#!/usr/bin/env python3
"""Black-box tests for the two HSBC RPA scripts, run through the HSBC_RPA_Test_Harness process.

Stdlib only; talks to the cluster exclusively through the c8ctl CLI (subprocess).
  python3 tests/rpa/run_rpa_tests.py                    # run all cases; S2/S6 cases pass simulatorScenario to the bot
  python3 tests/rpa/run_rpa_tests.py --manual-scenario  # do not pass simulatorScenario; prompt for S2/S6 instead
  python3 tests/rpa/run_rpa_tests.py --manual-scenario --no-prompt   # ... and skip the S2/S6 cases
  python3 tests/rpa/run_rpa_tests.py --cleanup          # delete all versions of HSBC_RPA_Test_Harness
Exit code 0 only if every executed case passed and no incident occurred.
"""
import argparse, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PID = "HSBC_RPA_Test_Harness"
RESULT_VAR = {"dqm": "dqmResult", "mivision": "mivisionResult", "echamps": "echampsResult"}


def c8(profile, *args):
    """Run c8ctl with --json and return (exit code, list of JSON values found in the output)."""
    r = subprocess.run(["c8ctl", "--profile", profile, *args, "--json"], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True)
    out, dec, vals, i = r.stdout, json.JSONDecoder(), [], 0
    while i < len(out):
        if out[i] in "[{":
            try:
                o, j = dec.raw_decode(out, i)
                vals.append(o)
                i = j
                continue
            except ValueError:
                pass
        i += 1
    return r.returncode, vals, out


def deploy(profile):
    files = [os.path.join(HERE, "rpa-harness.bpmn")] + sorted(
        os.path.join(ROOT, "process", "rpa", f) for f in os.listdir(os.path.join(ROOT, "process", "rpa")) if f.endswith(".rpa"))
    r = subprocess.run(["c8ctl", "--profile", profile, "deploy", *files], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if r.returncode != 0 or "Deployment successful" not in r.stdout:
        sys.exit("Deploy failed:\n" + r.stdout)
    print("Deployed:", ", ".join(os.path.basename(f) for f in files))


def pi_state(profile, key):
    for _ in range(5):
        _, vals, _ = c8(profile, "get", "pi", key)
        for v in vals:
            if isinstance(v, dict) and "state" in v:
                return v
        time.sleep(2)
    return None


def incidents(profile, key):
    _, vals, _ = c8(profile, "search", "inc", "--processInstanceKey", key)
    return [x for v in vals if isinstance(v, list) for x in v]


def cancel(profile, key):
    c8(profile, "cancel", "pi", key)


def result_var(profile, key, name):
    for _ in range(6):  # search index may lag behind completion
        _, vals, _ = c8(profile, "search", "vars", "--processInstanceKey", key, "--fullValue")
        for lst in (v for v in vals if isinstance(v, list)):
            for v in lst:
                if v.get("Name") == name and str(v.get("Scope Key")) == str(key):
                    return json.loads(v["Value"])
        time.sleep(2)
    return None


def match(exp, act, path, errs):
    """Field-by-field comparison. exp dict -> subset match; list of dicts -> same length, elementwise subset;
    list of scalars containing the literal alternatives (when act is scalar) -> any-of."""
    if isinstance(exp, dict) and set(exp) == {"$contains"}:
        if not isinstance(act, str) or exp["$contains"] not in act:
            errs.append(f"{path}: expected text containing {exp['$contains']!r}, got {act!r}")
    elif isinstance(exp, dict):
        if not isinstance(act, dict):
            errs.append(f"{path}: expected object, got {act!r}")
            return
        for k, v in exp.items():
            match(v, act.get(k), f"{path}.{k}" if path else k, errs)
    elif exp == "$notnull":
        if act is None:
            errs.append(f"{path}: expected a value, got null")
    elif isinstance(exp, list) and not isinstance(act, list):
        if act not in exp:
            errs.append(f"{path}: expected one of {exp}, got {act!r}")
    elif isinstance(exp, list):
        if not isinstance(act, list):
            errs.append(f"{path}: expected a list, got {act!r}")
            return
        if len(exp) != len(act):
            errs.append(f"{path}: expected {len(exp)} item(s), got {len(act)}")
        for i, (e, a) in enumerate(zip(exp, act)):
            match(e, a, f"{path}[{i}]", errs)
    else:
        if exp != act or type(exp) != type(act) and not (isinstance(exp, (int, float)) and isinstance(act, (int, float)) and not isinstance(act, bool)):
            errs.append(f"{path}: expected {exp!r}, got {act!r}")


def check(case, res):
    errs = []
    match(case["expected"], res, "", errs)
    ev = res.get("evidence") or {}
    if SCENARIO[0] and ((ev.get("simulatorScenario") or {}).get("selected") != SCENARIO[0]):
        errs.append(f"evidence.simulatorScenario.selected: expected {SCENARIO[0]!r}, got {ev.get('simulatorScenario')!r}")
    pages = ev.get("pagesVisited") or []
    if not pages:
        errs.append("evidence.pagesVisited is empty")
    for p in case.get("expectPagesVisited", []):
        if p not in pages:
            errs.append(f"evidence.pagesVisited lacks {p}")
    shots = {s.get("name"): s for s in ev.get("screenshots") or []}
    for n in case.get("expectScreenshots", []):
        s = shots.get(n)
        doc = (s or {}).get("document") or {}
        if not s:
            errs.append(f"evidence.screenshots lacks {n}")
        elif not doc.get("documentId") or (doc.get("metadata") or {}).get("contentType") != "image/png":
            errs.append(f"screenshot {n} is not an uploaded image/png document (error: {s.get('error')})")
    return errs


SCENARIO = [None]  # simulatorScenario passed to every script of the running case (None = do not select)


def run_case(profile, case, timeout):
    """Returns (verdict, detail, actual result dict or None). A 'Script not found' incident right after a
    deployment (the worker has not fetched the new RPA version yet) is retried once and reported in the detail."""
    verdict, detail, res = _run_case(profile, case, timeout)
    if verdict == "FAIL" and "INCIDENT" in detail and "Script not found" in detail:
        time.sleep(15)
        verdict, detail, res = _run_case(profile, case, timeout)
        detail = "(retried after 'Script not found' incident) " + detail
    return verdict, detail, res


def _run_case(profile, case, timeout):
    key = None
    for _ in range(3):  # the API occasionally answers 401/5xx for a single call
        code, vals, out = c8(profile, "create", "pi", "--id", PID, "--variables", json.dumps({"target": case["target"], **case["input"], **({"simulatorScenario": SCENARIO[0]} if SCENARIO[0] else {})}))
        key = next((v["key"] for v in vals if isinstance(v, dict) and "key" in v), None)
        if key:
            break
        time.sleep(3)
    if not key:
        return "FAIL", "could not start instance: " + out.strip()[-200:], None
    deadline, st = time.time() + timeout, None
    try:
        while time.time() < deadline:
            st = pi_state(profile, key)
            if st and (st["state"] != "ACTIVE" or st["hasIncident"]):
                break
            time.sleep(3)
        else:
            return "FAIL", f"timed out after {timeout}s (instance {key} cancelled)", None
        if st["hasIncident"]:
            inc = incidents(profile, key)
            msg = "; ".join(f"{i.get('Type', '')}: {str(i.get('Message', ''))[:150]}" for i in inc) or "incident"
            return "FAIL", f"INCIDENT on {key}: {msg}", None
        if st["state"] != "COMPLETED":
            return "FAIL", f"instance {key} ended {st['state']}", None
        res = result_var(profile, key, RESULT_VAR[case["target"]])
        if res is None:
            return "FAIL", f"instance {key} completed without {RESULT_VAR[case['target']]}", None
        errs = check(case, res)
        extra = f" errorMessage={res.get('errorMessage')!r}" if res.get("status") == "ERROR" else ""
        return ("FAIL", f"[{key}] " + " | ".join(errs) + extra, res) if errs else ("PASS", f"[{key}] status={res.get('status')} notFound={res.get('notFoundParameter')}", res)
    finally:
        s2 = pi_state(profile, key)
        if s2 and s2["state"] == "ACTIVE":
            cancel(profile, key)


def resolve_refs(inp, results):
    out = {}
    for k, v in inp.items():
        if isinstance(v, str) and v.startswith("$") and "." in v:
            tgt, field = v[1:].split(".", 1)
            out[k] = (results.get(tgt) or {}).get(field)
            if out[k] is None:
                out[k] = ""
        else:
            out[k] = v
    return out


def run_chain(profile, case, timeout):
    """A case with 'steps' runs them in order; each step's input may reference earlier results as $target.field."""
    results, details = {}, []
    for step in case["steps"]:
        step = {**step, "input": resolve_refs(step["input"], results)}
        verdict, detail, res = run_case(profile, step, timeout)
        details.append(f"{step['target']}:{verdict} {detail}")
        if verdict != "PASS" or res is None:
            return "FAIL", " || ".join(details), None
        results[step["target"]] = res
    return "PASS", " -> ".join(d.split(" ", 1)[0] for d in details), None


def cleanup(profile):
    # cancel any running harness instance first, otherwise the definition cannot be deleted
    _, vals, _ = c8(profile, "search", "pi", "--id", PID, "--state", "ACTIVE")
    for lst in (v for v in vals if isinstance(v, list)):
        for pi in lst:
            cancel(profile, str(pi["Key"]))
    exe = os.path.realpath(shutil.which("c8ctl"))
    pkg = os.path.dirname(os.path.dirname(exe))
    r = subprocess.run(["node", os.path.join(HERE, "delete_definitions.mjs"), pkg, profile, PID], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(r.stdout.strip())
    return r.returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", default="hsbc-cards")
    ap.add_argument("--cases", default=os.path.join(HERE, "cases.json"))
    ap.add_argument("--only", nargs="*", help="run only these case names")
    ap.add_argument("--manual-scenario", action="store_true", help="do not pass simulatorScenario to the scripts (demo-only simulator plumbing); ask the operator to select S2/S6 on the simulator home page instead")
    ap.add_argument("--no-prompt", action="store_true", help="with --manual-scenario: skip cases that need S2/S6 instead of prompting")
    ap.add_argument("--cleanup", action="store_true", help="delete all versions of " + PID + " and exit")
    ap.add_argument("--no-deploy", action="store_true")
    ap.add_argument("--timeout", type=int, default=360, help="seconds per case")
    a = ap.parse_args()
    if a.cleanup:
        sys.exit(cleanup(a.profile))
    cases = json.load(open(a.cases))["cases"]
    if a.only:
        cases = [c for c in cases if c["name"] in a.only]
    if not a.no_deploy:
        deploy(a.profile)
    rows, failed = [], False
    for c in cases:
        need = c["requiredSimulatorScenario"]
        if not a.manual_scenario and need != "any":
            SCENARIO[0] = need
        else:
            SCENARIO[0] = None
        if a.manual_scenario and need != "any":
            if a.no_prompt:
                rows.append((c["name"], "SKIP", f"needs simulator scenario {need}"))
                continue
            input(f"[{c['name']}] Select scenario {need} on the simulator home page, then press Enter ")
        elif c.get("note") and a.manual_scenario and not a.no_prompt:
            print(f"[{c['name']}] note: {c['note']}")
        print(f"running {c['name']} ...", flush=True)
        verdict, detail, _ = (run_chain if "steps" in c else run_case)(a.profile, c, a.timeout)
        failed |= verdict == "FAIL"
        rows.append((c["name"], verdict, detail))
    w = max(len(r[0]) for r in rows) if rows else 10
    print("\n" + "case".ljust(w), "result", "detail")
    for n, v, d in rows:
        print(n.ljust(w), v.ljust(6), d)
    ran = [r for r in rows if r[1] != "SKIP"]
    print(f"\n{sum(r[1]=='PASS' for r in rows)} passed, {sum(r[1]=='FAIL' for r in rows)} failed, {sum(r[1]=='SKIP' for r in rows)} skipped")
    sys.exit(1 if failed or not ran else 0)


if __name__ == "__main__":
    main()
