#!/usr/bin/env python3
"""Test suite entry point for the HSBC Commercial Cards Camunda 8.9 models (playbook s15, DoD s21).

  python3 -I tests/run_all.py                 # phase A: static + dmn tables (offline) + FEEL expressions (cluster FEEL only)
  python3 -I tests/run_all.py --dmn           # phase B: DMN table tests on the cluster (needs the version 2 DMNs deployed)
  python3 -I tests/run_all.py --process       # phase B: direct sub-process starts (needs the full deployment; sends mail to the redirect only)
  python3 -I tests/run_all.py --coverage      # phase C: elements never reached by any HSBC instance (run after --process)
  python3 -I tests/run_all.py --all           # everything, in that order

Options: --quick (skip the null matrix for scripts/prompts), --only NAME (scenario/decision filter for --process/--dmn).
Exit code 0 only if every selected suite passed. Reports are written to tests/reports/*.json.
Python standard library only. Secrets are read from newcluster2/newClient222-env.sh (parsed, never sourced, never printed).
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(label, script, extra=()):
    print("\n=== %s ===" % label, flush=True)
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, script), *extra])
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dmn", action="store_true")
    ap.add_argument("--process", action="store_true")
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-expressions", action="store_true")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only")
    args = ap.parse_args()
    results = {}
    phase_b = args.dmn or args.process or args.coverage or args.all
    if args.all or not phase_b:
        results["static"] = run("static checks", "static/run_static.py")
        results["dmn tables (offline)"] = run("DMN case tables vs process/dmn (offline)", "dmn/run_dmn.py", ["--offline"])
        if not args.no_expressions:
            results["expressions"] = run("FEEL expressions", "expressions/run_expressions.py", ["--quick"] if args.quick else [])
    only = ["--only", args.only] if args.only else []
    if args.all or args.dmn:
        results["dmn"] = run("DMN tables on the cluster", "dmn/run_dmn.py", only)
    if args.all or args.process:
        results["process"] = run("process tests", "process/run_process.py", only)
    if args.all or args.coverage:
        results["coverage"] = run("coverage", "coverage.py")
    print("\n=== summary ===")
    for k, v in results.items():
        print("  %-24s %s" % (k, "PASS" if v else "FAIL"))
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
