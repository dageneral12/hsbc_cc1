#!/usr/bin/env python3
"""DMN table tests (playbook s15 layer 4): one case per rule, plus invariants.

Evaluates against the deployed decisions with POST /v2/decision-definitions/evaluation. Needs the current
(version 2) DMNs to be deployed; run it only after the deploy.  Decision ids, input names and rule counts are read
from process/dmn/*.dmn, and every rule index must have at least one case.
"""
import argparse
import concurrent.futures as cf
import glob
import itertools
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from tests.lib import bpmnx, common  # noqa: E402
from tests.dmn import cases  # noqa: E402

D = "{https://www.omg.org/spec/DMN/20191111/MODEL/}"


def load_dmns():
    out = {}
    for f in sorted(glob.glob(os.path.join(bpmnx.PROCESS_DIR, "dmn", "*.dmn"))):
        root = ET.parse(f).getroot()
        for d in root.iter(D + "decision"):
            t = d.find(D + "decisionTable")
            ins = []
            for i in t.findall(D + "input"):
                txt = i.find(D + "inputExpression").find(D + "text").text or ""
                ins.extend(bpmnx.free_variables("=" + txt))
            out[d.get("id")] = {
                "file": os.path.basename(f), "hit": t.get("hitPolicy"), "rules": len(t.findall(D + "rule")),
                "inputs": sorted(set(ins)), "outputs": [o.get("name") for o in t.findall(D + "output")],
            }
    return out


class Dmn:
    def __init__(self, rest, workers=6):
        self.rest = rest
        self.pool = cf.ThreadPoolExecutor(max_workers=workers)
        self.cache = {}

    def _eval(self, did, variables):
        code, out = self.rest.post("/v2/decision-definitions/evaluation", {"decisionDefinitionId": did, "variables": variables})
        return code, out

    def submit(self, did, variables):
        key = (did, json.dumps(variables, sort_keys=True))
        if key not in self.cache:
            self.cache[key] = self.pool.submit(self._eval, did, variables)
        return self.cache[key]


def normalise(info, out):
    """-> (output value normalised to {name: value} or list of those, [matched rule indexes] or None)."""
    if not isinstance(out, dict):
        return None, None
    o = out.get("output")
    # The v2 REST API returns the decision output as a JSON-encoded string.
    if isinstance(o, str):
        try:
            o = json.loads(o)
        except ValueError:
            pass
    names = info["outputs"]
    if info["hit"] == "COLLECT":
        o = [] if o is None else o
        # A single-output COLLECT returns a plain list of values; keep it that way, as the BPMN reads it.
        if len(names) != 1:
            o = [x if isinstance(x, dict) else {names[0]: x} for x in o]
    elif o is not None and not isinstance(o, dict) and len(names) == 1:
        o = {names[0]: o}
    rules = None
    for ed in out.get("evaluatedDecisions", []) or []:
        mr = ed.get("matchedRules")
        if mr is not None and ed.get("decisionDefinitionId", ed.get("decisionId")) in (None, out.get("decisionDefinitionId")):
            rules = [m.get("ruleIndex") for m in mr]
    return o, rules


def offline():
    rep = common.Reporter("dmn-tables")
    models = load_dmns()
    for did, info in sorted(models.items()):
        rows = cases.ALL.get(did)
        if rows is None:
            rep.fail(did, "no case table")
            continue
        covered = set()
        for name, v, expected, rule in rows:
            extra = set(v) - set(info["inputs"])
            if extra:
                rep.fail("%s :: %s" % (did, name), "not inputs of the decision: %s" % sorted(extra))
            covered.update(rule if isinstance(rule, list) else [rule])
            bad = [r for r in (rule if isinstance(rule, list) else [rule]) if r > info["rules"]]
            if bad:
                rep.fail("%s :: %s" % (did, name), "rule index %s beyond the %d rules in the table" % (bad, info["rules"]))
        miss = [i for i in range(1, info["rules"] + 1) if i not in covered]
        rep.check("%s :: %d rules, %d cases, inputs %s" % (did, info["rules"], len(rows), info["inputs"]), not miss, "rules without a case: %s" % miss, "all rules have a case")
    return 0 if rep.summary() else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--min-version", type=int, default=1, help="fail if a decision's latest deployed version is lower")
    ap.add_argument("--only", help="decision id")
    ap.add_argument("--offline", action="store_true", help="only check the case tables against process/dmn (no cluster access)")
    args = ap.parse_args()
    if args.offline:
        return offline()
    rest = common.Rest()
    rep = common.Reporter("dmn")
    dmn = Dmn(rest, args.workers)
    models = load_dmns()

    # model <-> case table consistency and deployed versions
    for did in sorted(models):
        if did not in cases.ALL:
            rep.fail("dmn %s" % did, "no case table in tests/dmn/cases.py")
    for did in cases.ALL:
        if did not in models:
            rep.fail("dmn %s" % did, "case table for a decision that is not in process/dmn")
    versions = {}
    for did in models:
        items = rest.search("decision-definitions", {"decisionDefinitionId": did}, 50)
        versions[did] = max([int(i.get("version", 0)) for i in items] or [0])
        if versions[did] == 0:
            rep.fail("deployed %s" % did, "decision is not deployed")
        elif versions[did] < args.min_version:
            rep.fail("deployed %s" % did, "latest deployed version is %d, expected >= %d (deploy version 2 first)" % (versions[did], args.min_version))
        else:
            rep.ok("deployed %s" % did, "latest version %d" % versions[did])
    print("deployed decision versions: " + ", ".join("%s=v%d" % (k, v) for k, v in sorted(versions.items())))

    results = {}  # did -> list of (name, vars, output, rules)
    for did, rows in cases.ALL.items():
        if did not in models or (args.only and args.only != did):
            continue
        info = models[did]
        covered = set()
        futs = [dmn.submit(did, r[1]) for r in rows]
        results[did] = []
        for r, fut in zip(rows, futs):
            name, v, expected, rule = r
            cid = "%s :: %s" % (did, name)
            extra = set(v) - set(info["inputs"])
            if extra:
                rep.fail(cid, "case uses variables that are not inputs of the decision: %s" % sorted(extra))
                continue
            code, out = fut.result()
            if code != 200:
                rep.fail(cid, "HTTP %s %s" % (code, json.dumps(out)[:200]))
                continue
            o, rules = normalise(info, out)
            results[did].append((name, v, o, rules))
            problems = []
            if not common.match(expected, o):
                problems.append("output %s != expected %s" % (json.dumps(o)[:200], json.dumps(expected)[:160]))
            if rules is not None:
                want = rule if isinstance(rule, list) else [rule]
                if rules != want:
                    problems.append("matched rule(s) %s, expected %s" % (rules, want))
                covered.update(rules)
            else:
                covered.update(rule if isinstance(rule, list) else [rule])
            (rep.fail if problems else rep.ok)(cid, "; ".join(problems))
        missing = [i for i in range(1, info["rules"] + 1) if i not in covered]
        rep.check("%s :: every rule has a case" % did, not missing, "rules without a passing-or-run case: %s" % missing)

    def run_grid(did, grid_vars, base):
        keys = list(grid_vars)
        combos = [dict(zip(keys, c)) for c in itertools.product(*[grid_vars[k] for k in keys])]
        futs = [(c, dmn.submit(did, {**base, **c})) for c in combos]
        out = []
        for c, f in futs:
            code, o = f.result()
            n, _r = normalise(models[did], o) if code == 200 else (None, None)
            out.append((c, code, n))
        return out

    if not args.only or args.only == "TriageRouting":
        # null inputs never produce a wrong non-escalation route
        for inp, route in cases.TR_NULL_INPUTS.items():
            code, out = dmn.submit("TriageRouting", {**cases.TR_BASE, inp: None}).result()
            n, rules = normalise(models["TriageRouting"], out) if code == 200 else (None, None)
            got = (n or {}).get("triageRoute")
            rep.check("TriageRouting invariant :: %s=null escalates" % inp, got == route,
                      "route %s, expected %s (a null fact must escalate, never act)" % (got, route))
        grid = run_grid("TriageRouting", cases.TRIAGE_GRID, cases.TR_BASE)
        bad = []
        for c, code, n in grid:
            route = (n or {}).get("triageRoute")
            if code != 200 or route is None:
                bad.append("%s -> HTTP %s/no route" % (c, code))
                continue
            if route in cases.TR_ACTING and not (c["rpaStatus"] == "OK" and c["clientFound"] is True and c["senderAuthorised"] is True and c["cardFound"] is True):
                bad.append("%s -> %s (acting route without confirmed facts)" % (c, route))
        rep.check("TriageRouting invariant :: CVV/FRAUD routes need rpaStatus OK + client found + sender authorised + card found (%d combinations)" % len(grid),
                  not bad, "; ".join(bad[:5]) + (" (+%d)" % (len(bad) - 5) if len(bad) > 5 else ""))
        # recordNotFound false/null must never yield RECORD_NOT_FOUND with no notFoundReason
        bad = []
        for rnf in (False, None):
            for sc in ("INCORRECT_CVV", "FRAUD_ALERT"):
                code, out = dmn.submit("TriageRouting", {**cases.TR_BASE, "scenario": sc, "recordNotFound": rnf}).result()
                n, _ = normalise(models["TriageRouting"], out)
                if (n or {}).get("triageRoute") == "RECORD_NOT_FOUND":
                    bad.append("scenario=%s recordNotFound=%s" % (sc, rnf))
        rep.check("TriageRouting invariant :: rule-17 regression (recordNotFound false/null never RECORD_NOT_FOUND)", not bad, "; ".join(bad))

    if not args.only or args.only == "MentorApprovalDecision":
        grid = run_grid("MentorApprovalDecision", {"mentorDecision": cases.MENTOR_DECISIONS, "reworkCount": cases.MENTOR_REWORK, "maxRework": cases.MENTOR_MAX}, {})
        bad = []
        for c, code, n in grid:
            a = (n or {}).get("nextAction")
            d, rc, mx = c["mentorDecision"], c["reworkCount"], c["maxRework"]
            if a not in ("SEND", "REDRAFT", "CANCEL", "ESCALATE"):
                bad.append("%s -> %s" % (c, a))
            elif a == "SEND" and d != "APPROVE":
                bad.append("%s -> SEND without an exact APPROVE" % c)
            elif a == "REDRAFT" and not (d == "REWORK" and rc is not None and mx is not None and rc < mx):
                bad.append("%s -> REDRAFT outside the rework budget" % c)
            elif d == "APPROVE" and a != "SEND":
                bad.append("%s -> APPROVE did not SEND" % c)
        rep.check("MentorApprovalDecision invariant :: SEND only on APPROVE, REDRAFT only within budget, anything unknown escalates (%d combinations)" % len(grid),
                  not bad, "; ".join(bad[:5]))

    if not args.only or args.only == "RecordNotFoundAction":
        grid = run_grid("RecordNotFoundAction", {
            "notFoundReason": [None, "CUSTOMER_NOT_FOUND", "CLIENT_NOT_FOUND", "CARD_NOT_FOUND", "NO_MATCHING_AUTH", "BOGUS"],
            "detailsComplete": [True, False, None], "priorFollowUps": [None, 0, 1, 2]}, {"lookupAttempts": 1})
        bad = []
        for c, code, n in grid:
            n = n or {}
            a = n.get("notFoundAction")
            if a not in ("REQUEST_COMPLETE_DETAILS", "ESCALATE_RECORD_NOT_FOUND") or not n.get("notFoundGuidance"):
                bad.append("%s -> %s" % (c, a))
            elif a == "REQUEST_COMPLETE_DETAILS" and c["priorFollowUps"] != 0:
                bad.append("%s -> emails again after a prior follow-up / unknown count" % c)
            elif a == "REQUEST_COMPLETE_DETAILS" and c["notFoundReason"] in ("CLIENT_NOT_FOUND", None, "BOGUS", "CARD_NOT_FOUND") and c["detailsComplete"] is not False:
                bad.append("%s -> emails without grounds" % c)
            elif c["notFoundReason"] == "CLIENT_NOT_FOUND" and a != "ESCALATE_RECORD_NOT_FOUND":
                bad.append("%s -> CLIENT_NOT_FOUND must never email" % c)
        rep.check("RecordNotFoundAction invariant :: never emails twice, never emails on a system mismatch, null escalates (%d combinations)" % len(grid),
                  not bad, "; ".join(bad[:5]))

    if not args.only or args.only == "FraudManagementOutcome":
        grid = run_grid("FraudManagementOutcome", {
            "fraudTeamDecision": ["BLOCK_REMOVED", "KEEP_BLOCK_REISSUE", "UNCLEAR", "MORE_INFO_REQUIRED", None, "null", "x"],
            "interpretationConfidence": [None, 0, 0.5, 0.79, 0.8, 0.95, 1]}, {})
        bad = []
        for c, code, n in grid:
            n = n or {}
            auto = n.get("needsHumanReview") is False
            decisive = c["fraudTeamDecision"] in ("BLOCK_REMOVED", "KEEP_BLOCK_REISSUE")
            conf = c["interpretationConfidence"]
            if n.get("needsHumanReview") not in (True, False):
                bad.append("%s -> %s" % (c, n))
            elif auto and not (decisive and conf is not None and conf >= 0.8):
                bad.append("%s -> automatic outcome without a decisive, confident reading" % c)
            elif auto and not n.get("communicationPurpose"):
                bad.append("%s -> automatic with no communication purpose" % c)
            elif not auto and decisive and conf is not None and conf >= 0.8:
                bad.append("%s -> confident decisive reading still sent to a human" % c)
        rep.check("FraudManagementOutcome invariant :: automatic only for a decisive reading with confidence >= 0.8 (%d combinations)" % len(grid),
                  not bad, "; ".join(bad[:5]))

    if not args.only or args.only == "CustomerResponseType":
        bad = []
        for name, v, o, rules in results.get("CustomerResponseType", []):
            o = o or {}
            if o.get("recipientType") in ("SENDER", "AUTHORISED_CONTACT") and o.get("requiresMentorApproval") is not True:
                bad.append("%s: customer-facing without Mentor approval" % name)
            if o.get("recipientType") == "FRAUD_TEAM" and v["communicationPurpose"] != "FRAUD_TEAM_REVIEW_REQUEST":
                bad.append("%s: fraud-team recipient for a customer purpose" % name)
            if not o.get("messageGuidance"):
                bad.append("%s: empty guidance" % name)
            if o.get("recipientType") == "NONE" and o.get("caseStatusAfterSend") != "ESCALATED":
                bad.append("%s: unsupported purpose must escalate" % name)
        rep.check("CustomerResponseType invariant :: every customer-facing purpose needs Mentor approval; unsupported purposes escalate",
                  not bad, "; ".join(bad[:5]))

    ok = rep.summary()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
