"""Offline tests (no Meko needed): sandbox, policy brain, learning format. Run: python -m unittest -v"""
import unittest

from nightshift.bench import BASE
from nightshift.brain import PolicyBrain, interpret
from nightshift.crew import Briefing, Crew, learning_text, parse_learning
from nightshift.sandbox import DIAG_ORDER, SCENARIOS, Incident, fmt_action, parse_action


class Sandbox(unittest.TestCase):
    def test_every_scenario_is_solvable_and_deterministic(self):
        for key, s in SCENARIOS.items():
            a, b = Incident(s, seed=3), Incident(s, seed=3)
            self.assertEqual(a.diagnose(s.gun_tool), b.diagnose(s.gun_tool), key)
            if s.guard:
                self.assertFalse(a.act(s.fix["action"], s.fix["args"])["ok"], key)
                self.assertTrue(a.act(s.guard["action"], s.guard["args"])["ok"], key)
            self.assertTrue(a.act(s.fix["action"], s.fix["args"])["ok"], key)
            self.assertTrue(a.resolved, key)

    def test_wrong_fix_costs_time_and_is_counted(self):
        i = Incident(SCENARIOS["pool-exhaustion"])
        self.assertFalse(i.act("rollback", {"service": "checkout-api"})["ok"])
        self.assertEqual(i.failed_actions, 1)
        self.assertFalse(i.resolved)

    def test_only_the_gun_tool_points_at_the_real_fix(self):
        for key, s in SCENARIOS.items():
            i = Incident(s, seed=1)
            found = [t for t in DIAG_ORDER if any(h[0] == s.fix["action"] for h in interpret(t, i.diagnose(t), s.service))]
            self.assertEqual(found, [s.gun_tool], key)

    def test_action_roundtrip(self):
        self.assertEqual(parse_action(fmt_action("scale_pool", {"size": 80})), ("scale_pool", {"size": "80"}))


class ColdCrew(unittest.TestCase):
    def test_amnesiac_crew_resolves_everything(self):
        for key in SCENARIOS:
            r = Crew("t", None, PolicyBrain()).handle(SCENARIOS[key], 0, seed=1)
            self.assertTrue(r["resolved"], key)
            self.assertGreater(r["tokens"], 0)


class Learning(unittest.TestCase):
    def test_learning_text_roundtrip(self):
        t = learning_text("INC-0007", "alpha", "yugabyte", "disk full", "97% used", "disk_usage", ("purge_wal", {"node": "yb-node-2"}),
                          ("snapshot", {"node": "yb-node-2"}), [("restart", {"service": "yugabyte"})], ("scale_pool", {"size": 80}))
        L = parse_learning(t)
        self.assertEqual(L["fix"], ("purge_wal", {"node": "yb-node-2"}))
        self.assertEqual(L["guard"][0], "snapshot")
        self.assertEqual(L["dead"][0][0], "restart")
        self.assertEqual(L["replaces"][0], "scale_pool")
        self.assertEqual((L["incident"], L["shift"], L["service"], L["confirm"]), ("INC-0007", "alpha", "yugabyte", "disk_usage"))

    def _brief(self, action, args, confirm, service):
        cite = {"id": "m1", "label": "[1] INC-0001 learning (shift alpha)", "score": 0.9, "source": "shared learning"}
        return Briefing(playbooks=[{"action": action, "args": args, "confirm": confirm, "cite": cite, "service": service}])

    def _run(self, key, brief):
        s = SCENARIOS[key]
        inc, brain = Incident(s, seed=2), PolicyBrain()
        brain.reset({"alert": inc.alert, "service": s.service}, brief)
        brain.conflict, last, calls = None, None, []
        for _ in range(20):
            st = brain.next(last)
            if st["type"] == "diagnose":
                last = dict(st, output=inc.diagnose(st["tool"]))
            else:
                res = inc.act(st["action"], st["args"])
                last = dict(st, ok=res["ok"], message=res["message"])
                calls.append(st["action"])
                if inc.resolved:
                    break
        return inc, brain, calls

    def test_remembered_fix_is_confirmed_then_applied_in_one_diagnostic(self):
        inc, _, calls = self._run("pool-exhaustion", self._brief("scale_pool", {"size": "80"}, "pool_stats", "checkout-api"))
        self.assertTrue(inc.resolved)
        self.assertEqual((inc.diag_calls, calls, inc.failed_actions), (["pool_stats"], ["scale_pool"], 0))

    def test_memory_is_not_obeyed_when_evidence_disagrees(self):
        inc, _, calls = self._run("lookalike-slow-query", self._brief("scale_pool", {"size": "80"}, "pool_stats", "checkout-api"))
        self.assertTrue(inc.resolved)
        self.assertNotIn("scale_pool", calls)
        self.assertEqual(inc.failed_actions, 0)

    def test_stale_memory_is_overruled_by_live_evidence(self):
        inc, brain, calls = self._run("pool-exhaustion-migrated", self._brief("scale_pool", {"size": "80"}, "pool_stats", "checkout-api"))
        self.assertEqual(calls, ["set_conn_mgr"])
        self.assertEqual(brain.conflict["memory"]["action"], "scale_pool")

    def test_dead_end_from_a_ruled_out_learning_does_not_veto_live_evidence(self):
        # recall returns only the payments certificate learning, whose dead end is rollback;
        # tonight's fault is the bad deploy, where rollback is the fix
        brief = self._brief("renew_cert", {"domain": "payments.internal"}, "cert_check", "payments")
        brief.dead_ends.append({"action": "rollback", "args": {"service": "payments"}, "cite": brief.playbooks[0]["cite"]})
        inc, _, calls = self._run("bad-deploy", brief)
        self.assertTrue(inc.resolved)
        self.assertEqual(calls[-1], "rollback")

    def test_story_covers_all_base_scenarios(self):
        self.assertEqual(len(BASE), 12)


if __name__ == "__main__":
    unittest.main()
