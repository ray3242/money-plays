"""A deterministic production sandbox for on-call agents.

"Meridian" is a fictional e-commerce stack running on a 3-node YugabyteDB cluster. Each incident
breaks it in one specific way. Agents get the same read-only diagnostic tools and write actions a
human on-call would have. Diagnostics return realistic, noisy output (that is what costs tokens);
actions either repair the fault, do nothing useful, or are refused by a guardrail.

Nothing here knows about Meko: the sandbox is the world, not the memory.
"""
import random
import re
from dataclasses import dataclass, field

DIAGNOSTICS = [
    # name, simulated seconds a human/agent waits for it, what it shows
    ("metrics", 20, "golden signals (latency, errors, saturation) for the alerting service"),
    ("logs", 45, "last 40 log lines of the alerting service"),
    ("recent_deploys", 15, "deploys and feature-flag changes in the last 6 hours"),
    ("pool_stats", 20, "connection pooler statistics"),
    ("db_stats", 40, "YugabyteDB tablet, leader and slow-query statistics"),
    ("cache_stats", 20, "Redis memory and eviction statistics"),
    ("queue_stats", 20, "Kafka consumer group lag"),
    ("disk_usage", 15, "disk usage per node"),
    ("net_check", 30, "DNS and connectivity checks between services"),
    ("cert_check", 15, "TLS certificate expiry for internal endpoints"),
]
DIAG_SECONDS = {n: s for n, s, _ in DIAGNOSTICS}
DIAG_ORDER = [n for n, _, _ in DIAGNOSTICS]

ACTIONS = {
    "rollback": "roll a service back to its previous release (args: service)",
    "restart": "rolling restart of a service (args: service)",
    "scale_pool": "set pgbouncer default_pool_size (args: size)",
    "set_conn_mgr": "set YSQL connection manager max server connections (args: size)",
    "create_index": "create an index online (args: table, column)",
    "rebalance_leaders": "trigger tablet leader rebalancing (no args)",
    "split_tablet": "split the hot tablet of a table (args: table)",
    "cordon": "stop routing new work to a node (args: node)",
    "sync_clock": "force chrony resync on a node (args: node)",
    "set_cache_policy": "set Redis maxmemory-policy (args: policy)",
    "scale_consumers": "set consumer replicas of a group (args: group, n)",
    "renew_cert": "renew an internal TLS certificate (args: domain)",
    "snapshot": "take a storage snapshot of a node (args: node)",
    "purge_wal": "garbage-collect retained WAL segments (args: node)",
    "toggle_flag": "turn a feature flag on or off (args: flag, on)",
    "flush_dns": "flush the resolver cache of a service (args: service)",
}
ACTION_SECONDS = 60
FAILED_ACTION_PENALTY = 180  # a wrong change in prod costs time and risk


@dataclass
class Scenario:
    key: str
    service: str
    title: str
    alerts: list  # paraphrases: the same fault never pages with the exact same words
    root_cause: str
    gun_tool: str  # the diagnostic that shows the real cause
    gun_lines: list  # lines injected into that diagnostic
    fix: dict  # {"action": ..., "args": {...}}
    guard: dict = None  # action that must run first, or the fix is refused
    guard_reason: str = ""
    herring_tool: str = None  # a diagnostic that looks guilty but is not
    herring_lines: list = field(default_factory=list)
    refuses: dict = field(default_factory=dict)  # action -> refusal text (stale fixes)


S = Scenario
SCENARIOS = {
    s.key: s
    for s in [
        S(
            "pool-exhaustion", "checkout-api", "Connection pool exhausted",
            [
                "checkout-api p99 latency 4.2s (SLO 800ms), 12% of requests timing out",
                "PAGE: checkout is slow, customers report spinner on Pay button, p99 > 4s",
                "checkout-api upstream timeouts climbing, latency SLO burning fast",
            ],
            "pgbouncer default_pool_size (20) is too small since the worker count was doubled; clients queue for a server connection",
            "pool_stats",
            ["pool checkout_rw  cl_active=20 cl_waiting=143 sv_active=20 sv_idle=0 maxwait=38s", "WARNING pooler: 143 clients waiting, default_pool_size=20 saturated"],
            {"action": "scale_pool", "args": {"size": 80}},
            herring_tool="recent_deploys",
            herring_lines=["18m ago  deploy checkout-api v2.31.0 -> v2.31.1 (copy change on receipt page)"],
        ),
        S(
            "missing-index", "catalog", "Sequential scans after migration",
            [
                "catalog p95 latency 2.9s, YSQL CPU 94% on all tservers",
                "product pages loading slowly, catalog-api latency alarm firing",
            ],
            "migration 0193 dropped the index on order_items(customer_id); the recommendations query now does a full scan",
            "db_stats",
            ["slow query (avg 2710ms, 412 calls/min): SELECT ... FROM order_items WHERE customer_id = $1", "plan: Seq Scan on order_items (rows=48,112,907) - no usable index on customer_id"],
            {"action": "create_index", "args": {"table": "order_items", "column": "customer_id"}},
        ),
        S(
            "leader-imbalance", "yugabyte", "Tablet leaders piled on one node",
            [
                "yb-node-1 CPU 97% while yb-node-2 and yb-node-3 idle, write latency 600ms",
                "uneven load on the Yugabyte cluster: one tserver saturated, writes slow",
            ],
            "after the rolling restart all tablet leaders stayed on yb-node-1; leader balancing was left disabled",
            "db_stats",
            ["tablet leaders: yb-node-1=118 yb-node-2=1 yb-node-3=1 (expected ~40 each)", "load balancer: leader balancing DISABLED since rolling restart 02:10"],
            {"action": "rebalance_leaders", "args": {}},
            herring_tool="metrics",
            herring_lines=["yb-node-1 process restarts in last 6h: 1"],
        ),
        S(
            "clock-skew", "yugabyte", "Clock skew on one node",
            [
                "yb-node-3 tserver crash-looping, transactions aborting with conflict errors",
                "spike in aborted transactions on orders, yb-node-3 flapping",
            ],
            "chrony lost its upstream on yb-node-3; skew passed max_clock_skew_usec so the tserver kills itself",
            "logs",
            ["F tserver yb-node-3: Too big clock skew is detected: 612ms, while max allowed is: 500ms", "chronyd[811]: Can't synchronise: no selectable sources"],
            {"action": "sync_clock", "args": {"node": "yb-node-3"}},
            guard={"action": "cordon", "args": {"node": "yb-node-3"}},
            guard_reason="refused: yb-node-3 still serves traffic; cordon it before stepping its clock or in-flight transactions can read stale data",
        ),
        S(
            "redis-oom", "session-svc", "Redis out of memory",
            [
                "users randomly logged out, session-svc error rate 9%",
                "login loop reports from support, session lookups failing intermittently",
            ],
            "Redis hit maxmemory with policy noeviction, so new session writes are rejected",
            "cache_stats",
            ["used_memory=7.98G maxmemory=8.00G maxmemory_policy=noeviction", "rejected writes last 5m: 18,442 (OOM command not allowed when used memory > 'maxmemory')"],
            {"action": "set_cache_policy", "args": {"policy": "allkeys-lru"}},
            herring_tool="logs",
            herring_lines=["WARN session-svc: upstream timeout after 2000ms, worker 7 unresponsive, consider restart"],
        ),
        S(
            "kafka-lag", "billing", "Consumer lag on billing",
            [
                "invoices delayed by 40 minutes, billing-events consumer lag 1.9M",
                "customers not receiving receipts, billing pipeline behind",
            ],
            "the black-friday promo tripled event volume; 2 consumer replicas cannot keep up",
            "queue_stats",
            ["group billing-consumers topic billing-events lag=1,912,440 (+38k/min) members=2 partitions=12", "throughput per member at ceiling: 2.1k msg/s"],
            {"action": "scale_consumers", "args": {"group": "billing-consumers", "n": 6}},
        ),
        S(
            "cert-expiry", "payments", "Internal certificate expired",
            [
                "payments returning 502 for every charge, error budget gone in 6 minutes",
                "all card payments failing, gateway reports upstream handshake failure",
            ],
            "the internal certificate for payments.internal expired; cert-manager renewal was stuck",
            "cert_check",
            ["payments.internal  EXPIRED 00:14 ago  (notAfter passed)  issuer=meridian-internal-ca", "cert-manager: renewal for payments.internal stuck (challenge pending 3d)"],
            {"action": "renew_cert", "args": {"domain": "payments.internal"}},
            herring_tool="recent_deploys",
            herring_lines=["41m ago  deploy payments v9.4.2 -> v9.4.3 (dependency bump)"],
        ),
        S(
            "disk-wal", "yugabyte", "WAL filling the disk",
            [
                "yb-node-2 disk 97% full, writes will stop at 100%",
                "disk pressure alarm on yb-node-2, free space dropping 1% every 4 minutes",
            ],
            "a paused CDC stream pins WAL segments on yb-node-2, so they are never garbage-collected",
            "disk_usage",
            ["yb-node-2 /mnt/d0 97% used  (wal=412G data=118G)", "retained WAL held by cdc stream 'analytics-export' (paused 3d ago)"],
            {"action": "purge_wal", "args": {"node": "yb-node-2"}},
            guard={"action": "snapshot", "args": {"node": "yb-node-2"}},
            guard_reason="refused: policy requires a storage snapshot of the node before deleting WAL",
        ),
        S(
            "bad-flag", "pricing", "Feature flag regression",
            [
                "cart totals wrong for EU customers, pricing error rate 6%",
                "pricing-api 500s on checkout for some regions",
            ],
            "flag new_pricing_engine was turned on for 100% and it mishandles VAT-inclusive prices",
            "recent_deploys",
            ["26m ago  flag new_pricing_engine 10% -> 100% (by release-bot)"],
            {"action": "toggle_flag", "args": {"flag": "new_pricing_engine", "on": False}},
            herring_tool="logs",
            herring_lines=["WARN pricing: slow upstream, worker 3 unresponsive, consider restart"],
        ),
        S(
            "dns-stale", "search", "Stale DNS after failover",
            [
                "search returns no results, search-api cannot reach the index cluster",
                "empty search pages sitewide, search-api connection errors",
            ],
            "the index cluster failed over to a new address but search-api still caches the old record",
            "net_check",
            ["search-api -> index.internal: resolves 10.2.8.14 (cached, ttl ignored); authoritative answer is 10.2.9.31", "connect 10.2.8.14:9200: no route to host"],
            {"action": "flush_dns", "args": {"service": "search"}},
        ),
        S(
            "bad-deploy", "payments", "Crash after release",
            [
                "payments error rate 31% right after a release, refunds failing",
                "refund endpoint throwing 500s, payments pods restarting",
            ],
            "release v9.5.0 dereferences a null refund reason; every refund without a reason crashes the worker",
            "logs",
            ["ERROR payments v9.5.0: NullPointerException at RefundHandler.reason() (RefundHandler.java:88)", "pod payments-7f9 restarted 14 times since deploy of v9.5.0 (11m ago)"],
            {"action": "rollback", "args": {"service": "payments"}},
        ),
        S(
            "hot-shard", "cart", "Hot tablet",
            [
                "cart writes timing out during the flash sale, cart-api p99 3.1s",
                "add-to-cart failing intermittently, one tablet saturated",
            ],
            "cart_events is range-partitioned on a timestamp, so every write lands on the newest tablet",
            "db_stats",
            ["hot tablet: cart_events tablet 9f3c takes 96% of writes (11.2k ops/s), others idle", "table cart_events: range sharded on created_at, 1 of 24 tablets receiving inserts"],
            {"action": "split_tablet", "args": {"table": "cart_events"}},
        ),
        # Same page as pool-exhaustion, different cause: memory must be checked, not obeyed.
        S(
            "lookalike-slow-query", "checkout-api", "Looks like the pool, is a query",
            [
                "checkout-api p99 latency 3.8s, requests timing out on the Pay step",
            ],
            "a new checkout query filters checkout_sessions by cart_id without an index; the pool is healthy",
            "db_stats",
            ["slow query (avg 3320ms, 96 calls/min): SELECT ... FROM checkout_sessions WHERE cart_id = $1", "plan: Seq Scan on checkout_sessions (rows=9,480,221) - no usable index on cart_id"],
            {"action": "create_index", "args": {"table": "checkout_sessions", "column": "cart_id"}},
        ),
        # The remembered fix has gone stale: the pooler was replaced after the first incident.
        S(
            "pool-exhaustion-migrated", "checkout-api", "Pool exhausted, but the pooler changed",
            [
                "checkout-api p99 latency 4.5s, timeouts on Pay, clients waiting for connections",
            ],
            "the stack moved from pgbouncer to the built-in YSQL connection manager; its max server connections (30) is saturated",
            "pool_stats",
            ["ysql_conn_mgr pool checkout_rw  cl_active=30 cl_waiting=171 sv_active=30 sv_idle=0 maxwait=44s", "NOTE pgbouncer was retired in change CHG-2291; pooling is now ysql_conn_mgr (max_server_connections=30)"],
            {"action": "set_conn_mgr", "args": {"size": 120}},
            refuses={"scale_pool": "refused: pgbouncer is no longer deployed (retired in CHG-2291); use set_conn_mgr"},
        ),
    ]
}

# ---- noise generators: healthy-looking output that still has to be read -------------------
_SERVICES = ["checkout-api", "catalog", "payments", "search", "cart", "pricing", "billing", "session-svc"]
_LOG_NOISE = [
    "INFO  request_id={r} GET /healthz 200 {ms}ms",
    "INFO  request_id={r} POST /v1/{svc}/batch 200 {ms}ms bytes={b}",
    "DEBUG cache hit ratio 0.{p} over last 60s",
    "INFO  scheduled job compaction-check finished in {ms}ms",
    "WARN  retrying idempotent call to inventory (attempt 2) request_id={r}",
    "INFO  config reload: no changes detected",
    "DEBUG gc pause {ms}ms (young generation)",
    "INFO  request_id={r} GET /v1/{svc}/items?page={p} 200 {ms}ms",
]


def _noise(tool, service, rng):
    L = []
    if tool == "metrics":
        L.append(f"service={service} window=15m")
        for name in ["rps", "p50_ms", "p95_ms", "p99_ms", "error_rate_pct", "cpu_pct", "mem_pct", "open_fds", "gc_pause_ms", "threads"]:
            L.append(f"  {name:<16} now={rng.randint(10, 990):>5} 1h_avg={rng.randint(10, 990):>5} 24h_avg={rng.randint(10, 990):>5}")
        for n in ("yb-node-1", "yb-node-2", "yb-node-3"):
            L.append(f"  {n} cpu={rng.randint(20, 60)}% mem={rng.randint(40, 70)}% iowait={rng.randint(0, 6)}% net_in={rng.randint(10, 90)}MB/s")
    elif tool == "logs":
        for _ in range(38):
            L.append(
                f"2026-11-21T03:{rng.randint(10, 59)}:{rng.randint(10, 59)}Z {service} "
                + rng.choice(_LOG_NOISE).format(r=f"{rng.getrandbits(32):08x}", ms=rng.randint(2, 180), b=rng.randint(200, 9000), p=rng.randint(71, 99), svc=service)
            )
    elif tool == "recent_deploys":
        L.append("change log, last 6h")
        for _ in range(6):
            L.append(f"{rng.randint(65, 350)}m ago  deploy {rng.choice(_SERVICES)} v{rng.randint(1, 9)}.{rng.randint(0, 40)}.{rng.randint(0, 9)} (routine)")
        L.append(f"{rng.randint(65, 350)}m ago  flag dark_mode_banner 50% -> 60% (by growth-bot)")
    elif tool == "pool_stats":
        L.append("pooler SHOW POOLS")
        for svc in _SERVICES[:6]:
            L.append(f"pool {svc.replace('-', '_')}_ro  cl_active={rng.randint(2, 12)} cl_waiting=0 sv_active={rng.randint(2, 12)} sv_idle={rng.randint(3, 9)} maxwait=0s")
    elif tool == "db_stats":
        L.append("yb-admin / pg_stat_statements summary")
        L.append("tablet leaders: yb-node-1=40 yb-node-2=40 yb-node-3=40")
        L.append("load balancer: enabled, idle")
        for t in ["orders", "order_items", "customers", "cart_events", "inventory", "checkout_sessions", "payments_ledger"]:
            L.append(f"table {t:<18} tablets={rng.choice([12, 24, 48])} avg_read_ms={rng.randint(1, 9)} avg_write_ms={rng.randint(2, 12)} index_scans={rng.randint(90, 99)}%")
        for _ in range(4):
            L.append(f"query (avg {rng.randint(2, 40)}ms, {rng.randint(100, 4000)} calls/min): SELECT ... /* healthy */")
    elif tool == "cache_stats":
        L += ["redis INFO memory/stats", f"used_memory={rng.randint(21, 49) / 10}G maxmemory=8.00G maxmemory_policy=allkeys-lru", f"evicted_keys last 5m: {rng.randint(0, 40)}", f"keyspace_hits={rng.randint(10**6, 10**7)} keyspace_misses={rng.randint(10**4, 10**5)}", f"connected_clients={rng.randint(80, 300)} blocked_clients=0"]
    elif tool == "queue_stats":
        L.append("kafka consumer groups")
        for g in ["billing-consumers", "email-senders", "search-indexers", "audit-writers", "analytics-export"]:
            L.append(f"group {g} lag={rng.randint(0, 900)} members={rng.randint(2, 6)} partitions=12")
    elif tool == "disk_usage":
        for n in ("yb-node-1", "yb-node-2", "yb-node-3"):
            L.append(f"{n} /mnt/d0 {rng.randint(38, 61)}% used  (wal={rng.randint(8, 30)}G data={rng.randint(100, 130)}G)")
            L.append(f"{n} /var/log {rng.randint(10, 40)}% used")
    elif tool == "net_check":
        for a in _SERVICES[:5]:
            b = rng.choice(["yb-tserver.internal", "redis.internal", "kafka.internal", "index.internal"])
            L.append(f"{a} -> {b}: resolves ok, connect ok, rtt={rng.randint(1, 9)}ms")
    elif tool == "cert_check":
        for d in ["checkout.internal", "catalog.internal", "search.internal", "billing.internal", "payments.internal", "yb-tserver.internal"]:
            L.append(f"{d}  valid, expires in {rng.randint(20, 80)}d  issuer=meridian-internal-ca")
    return L


class Incident:
    """One live fault. Tracks every tool call so runs can be scored."""

    def __init__(self, scenario: Scenario, alert_variant=0, seed=0, incident_id="INC-0000"):
        self.s = scenario
        self.id = incident_id
        self.alert = scenario.alerts[alert_variant % len(scenario.alerts)]
        self.seed = seed
        self.resolved = False
        self.guard_done = scenario.guard is None
        self.sim_seconds = 0
        self.diag_calls = []
        self.action_calls = []
        self.failed_actions = 0

    # -- read-only ---------------------------------------------------------------------------
    def diagnose(self, tool):
        if tool not in DIAG_SECONDS:
            return f"unknown diagnostic '{tool}'"
        rng = random.Random(f"{self.seed}:{self.s.key}:{tool}")
        lines = _noise(tool, self.s.service, rng)
        extra = []
        if not self.resolved:
            if tool == self.s.gun_tool:
                extra += self.s.gun_lines
            if tool == self.s.herring_tool:
                extra += self.s.herring_lines
            if tool == "metrics":
                extra.append(f"ALERTING {self.s.service}: {self.alert}")
        for e in extra:
            lines.insert(rng.randint(1, max(1, len(lines))), e)
        self.sim_seconds += DIAG_SECONDS[tool]
        self.diag_calls.append(tool)
        return f"$ {tool} --service {self.s.service}\n" + "\n".join(lines)

    # -- writes ------------------------------------------------------------------------------
    def act(self, action, args=None):
        args = args or {}
        self.action_calls.append({"action": action, "args": args})
        self.sim_seconds += ACTION_SECONDS
        if action not in ACTIONS:
            return self._fail(f"unknown action '{action}'")
        if self.resolved:
            return {"ok": True, "message": "no-op: incident already resolved"}
        if action in self.s.refuses:
            return self._fail(self.s.refuses[action])
        if self.s.guard and action == self.s.guard["action"] and _args_match(args, self.s.guard["args"]):
            self.guard_done = True
            return {"ok": True, "message": f"{action} done"}
        if action == self.s.fix["action"] and _args_match(args, self.s.fix["args"]):
            if not self.guard_done:
                return self._fail(self.s.guard_reason)
            self.resolved = True
            return {"ok": True, "message": f"{action} applied; {self.s.service} recovering, alert cleared"}
        return self._fail(f"{action} completed but the alert is still firing: {self.alert}")

    def _fail(self, msg):
        self.failed_actions += 1
        self.sim_seconds += FAILED_ACTION_PENALTY
        return {"ok": False, "message": msg}

    def health(self):
        return "OK: alert cleared" if self.resolved else f"FIRING: {self.alert}"


def _args_match(given, want):
    def norm(v):
        return str(v).strip().lower()

    return all(norm(given.get(k)) == norm(v) for k, v in want.items())


def fmt_action(action, args=None):
    args = args or {}
    return f"{action}(" + ", ".join(f"{k}={v}" for k, v in args.items()) + ")"


_ACT_RE = re.compile(r"([a-z_]+)\(([^)]*)\)")


def parse_action(text):
    """Inverse of fmt_action: 'scale_pool(size=80)' -> ('scale_pool', {'size': '80'})."""
    m = _ACT_RE.search(text or "")
    if not m or m.group(1) not in ACTIONS:
        return None
    args = {}
    for part in filter(None, (p.strip() for p in m.group(2).split(","))):
        if "=" in part:
            k, v = part.split("=", 1)
            args[k.strip()] = v.strip()
    return m.group(1), args
