"""python -m nightshift <bench|serve|doctor>"""
import argparse
import json
import sys
import time

from .bench import run_story, table
from .meko import Meko, MekoError


def _meko(args, fresh=True):
    m = Meko(url=args.meko_url, api_key=args.api_key).connect()
    name = args.datapack or (f"nightshift-{int(time.time())}" if fresh else "nightshift")
    m.ensure_datapack(name)
    return m, name


def main(argv=None):
    ap = argparse.ArgumentParser(prog="nightshift", description="An on-call agent crew whose memory survives the shift change. Built on Meko.")
    ap.add_argument("--meko-url", help="Meko MCP endpoint (default: MEKO_URL, else Meko Cloud if MEKO_API_KEY is set, else local http://127.0.0.1:7777/mcp)")
    ap.add_argument("--api-key", help="Meko API key (default: MEKO_API_KEY, or the local `meko token`)")
    ap.add_argument("--datapack", help="datapack name to use (default: a fresh nightshift-<timestamp>)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bench", help="run three nights on call, with and without Meko, and print the numbers")
    b.add_argument("--quick", action="store_true", help="4 incident types instead of 12")
    b.add_argument("--out", help="write results + full event stream to this JSON file (also used by the static replay)")
    b.add_argument("--llm", action="store_true", help="use a real model (OPENAI_BASE_URL / OPENAI_API_KEY / NIGHTSHIFT_MODEL) instead of the deterministic policy")
    b.add_argument("-v", "--verbose", action="store_true")
    s = sub.add_parser("serve", help="live dashboard")
    s.add_argument("--port", type=int, default=8787)
    s.add_argument("--host", default="127.0.0.1")
    sub.add_parser("doctor", help="check the Meko connection and list the tools this deployment exposes")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "doctor":
            m, name = _meko(args, fresh=False)
            print(f"Connected to {m.url}\ndatapack '{name}' = {m.datapack_id}\n{len(m.tools)} tools: " + ", ".join(sorted(m.tools)))
            for t in ("track_token_usage", "selflearning_status", "memory_promote"):
                print(f"  {t}: {'yes' if m.has(t) else 'not exposed by this deployment (Nightshift degrades gracefully)'}")
            return 0
        if args.cmd == "serve":
            from .server import serve

            return serve(args)
        m, name = _meko(args)
        events = []

        def emit(e):
            events.append(e)
            if args.verbose and e["kind"] not in ("score",):
                print(f"  [{e['shift']}:{e['agent']}] {e['kind']}: {e['text'][:160]}")
            elif e["kind"] == "shift":
                print(e["text"])

        brain = None
        if args.llm:
            from .llm import LLMBrain

            brain = LLMBrain
        kw = {"brain_factory": brain} if brain else {}
        out = run_story(m, emit=emit, quick=args.quick, **kw)
        out.update(events=events, datapack=name, meko_url=m.url, meko_calls=len(m.calls), generated_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"))
        print()
        print(table(out["summary"]))
        print(f"\nTokens counted with: {out['token_method']}. Brain: {out['brain']}. Meko calls made: {len(m.calls)}. Datapack: {name} (open the Meko UI to browse it).")
        if args.out:
            json.dump(out, open(args.out, "w"), indent=1)
            print(f"Wrote {args.out}")
        return 0
    except MekoError as e:
        print(f"Meko error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
