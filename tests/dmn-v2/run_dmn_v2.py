#!/usr/bin/env python3
"""DMN table tests for the v2 agentic build (process-v2/dmn). Separate from tests/dmn so the v12 suite is unaffected.

  python3 -I tests/dmn-v2/run_dmn_v2.py --offline   # table/case consistency, no cluster access
  python3 -I tests/dmn-v2/run_dmn_v2.py             # evaluates every case on the cluster (needs process-v2 deployed)
  --only DECISION_ID to run one decision.
Reports go to tests/reports/dmn-v2*.json.
"""
import argparse
import glob
import json
import os
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
from tests.lib import bpmnx, common  # noqa: E402
from tests.dmn.run_dmn import Dmn, normalise  # noqa: E402
import cases_v2 as cases  # noqa: E402

D = "{https://www.omg.org/spec/DMN/20191111/MODEL/}"
V2_DIR = os.path.join(bpmnx.ROOT, "process-v2", "dmn")


def load_dmns():
    out = {}
    for f in sorted(glob.glob(os.path.join(V2_DIR, "*.dmn"))):
        root = ET.parse(f).getroot()
        for d in root.iter(D + "decision"):
            t = d.find(D + "decisionTable")
            ins = []
            for i in t.findall(D + "input"):
                txt = i.find(D + "inputExpression").find(D + "text").text or ""
                ins.extend(bpmnx.free_variables("=" + txt))
            out[d.get("id")] = {"file": os.path.basename(f), "hit": t.get("hitPolicy"), "rules": len(t.findall(D + "rule")),
                                "inputs": sorted(set(ins)), "outputs": [o.get("name") for o in t.findall(D + "output")]}
    return out


def offline():
    rep = common.Reporter("dmn-v2-offline")
    models = load_dmns()
    for did in sorted(cases.ALL):
        if did not in models:
            rep.fail(did, "case table for a decision that is not in process-v2/dmn")
    for did, info in sorted(models.items()):
        rows = cases.ALL.get(did)
        if rows is None:
            rep.skip(did, "unchanged v12 decision (byte-identical copy), covered by tests/dmn")
            continue
        covered = set()
        for name, v, expected, rule in rows:
            extra = set(v) - set(info["inputs"])
            if extra:
                rep.fail("%s :: %s" % (did, name), "not inputs of the decision: %s" % sorted(extra))
            covered.add(rule)
            if rule > info["rules"]:
                rep.fail("%s :: %s" % (did, name), "rule index %s beyond the %d rules in the table" % (rule, info["rules"]))
        miss = [i for i in range(1, info["rules"] + 1) if i not in covered]
        rep.check("%s :: %d rules, %d cases, inputs %s" % (did, info["rules"], len(rows), info["inputs"]), not miss, "rules without a case: %s" % miss, "all rules have a case")
    return 0 if rep.summary() else 1


def live(only, workers):
    rest = common.Rest()
    rep = common.Reporter("dmn-v2")
    dmn = Dmn(rest, workers)
    models = load_dmns()
    for did, rows in cases.ALL.items():
        if only and only != did:
            continue
        info = models[did]
        covered = set()
        futs = [dmn.submit(did, r[1]) for r in rows]
        for (name, v, expected, rule), fut in zip(rows, futs):
            cid = "%s :: %s" % (did, name)
            code, out = fut.result()
            if code != 200:
                rep.fail(cid, "HTTP %s %s" % (code, json.dumps(out)[:200]))
                continue
            o, rules = normalise(info, out)
            problems = []
            if not common.match(expected, o):
                problems.append("output %s != expected %s" % (json.dumps(o)[:220], json.dumps(expected)[:200]))
            if rules is not None:
                if rules != [rule]:
                    problems.append("matched rule(s) %s, expected %s" % (rules, [rule]))
                covered.update(rules)
            else:
                covered.add(rule)
            (rep.fail if problems else rep.ok)(cid, "; ".join(problems))
        miss = [i for i in range(1, info["rules"] + 1) if i not in covered]
        rep.check("%s :: every rule matched by a case" % did, not miss, "rules never matched: %s" % miss)
    # invariants
    if not only or only == "MentorApprovalDecisionV2":
        bad = []
        for dec in cases.v12.MENTOR_DECISIONS:
            for rc in cases.v12.MENTOR_REWORK:
                for src in ("AGENT", "MODEL", None):
                    code, out = dmn.submit("MentorApprovalDecisionV2", {"mentorDecision": dec, "reworkCount": rc, "maxRework": 3, "draftSource": src}).result()
                    n, _ = normalise(models["MentorApprovalDecisionV2"], out) if code == 200 else (None, None)
                    a = (n or {}).get("nextAction")
                    if a == "SEND" and dec != "APPROVE":
                        bad.append((dec, rc, src, a))
                    if src == "AGENT" and dec in ("REWORK", "REJECT") and a != "RETURN_TO_CALLER":
                        bad.append((dec, rc, src, a))
                    if src != "AGENT" and a == "RETURN_TO_CALLER":
                        bad.append((dec, rc, src, a))
                    if a not in ("SEND", "REDRAFT", "CANCEL", "ESCALATE", "RETURN_TO_CALLER"):
                        bad.append((dec, rc, src, a))
        rep.check("MentorApprovalDecisionV2 invariant :: SEND only on APPROVE; AGENT REWORK/REJECT always return to the agent; RETURN_TO_CALLER only in AGENT mode", not bad, str(bad[:5]))
    if not only or only == "CustomerEmailPolicy":
        bad = []
        for purpose in ["MISSING_CARD_DETAILS", "CVV_RETRY_ADVICE", "FRAUD_OUTCOME_BLOCK_REMOVED", "FRAUD_OUTCOME_KEEP_BLOCK", "HUMAN_ACTION_UPDATE", "STATUS_UPDATE", None, "X"]:
            for closed in (True, False, None):
                for esc in (True, False):
                    code, out = dmn.submit("CustomerEmailPolicy", {**cases.CEP_BASE, "purpose": purpose, "closeAccepted": closed, "mentorEscalationOpen": esc}).result()
                    n, _ = normalise(models["CustomerEmailPolicy"], out) if code == 200 else (None, None)
                    if (closed is True or esc is True) and (n or {}).get("allowed") is not False:
                        bad.append((purpose, closed, esc, n))
        rep.check("CustomerEmailPolicy invariant :: nothing is allowed after closure or while a Mentor escalation is open", not bad, str(bad[:5]))
    if not only or only == "CaseCloseValidation":
        bad = []
        for outc in ["RESOLVED", "CLOSED_NO_RESPONSE", "OUT_OF_SCOPE", "ESCALATED", None, "X"]:
            for ures in (None, True, False):
                for team in (None, "RESOLVED_BY_TEAM", "RETURN_TO_AGENT", "CLOSE_ESCALATED"):
                    code, out = dmn.submit("CaseCloseValidation", {"outcome": outc, "resolvingEmailSent": None, "lastAwaitTimedOut": None, "lastEmailWasClarification": None,
                                                                   "latestScenario": None, "teamDecision": team, "unansweredReply": ures}).result()
                    n, _ = normalise(models["CaseCloseValidation"], out) if code == 200 else (None, None)
                    acc = (n or {}).get("accepted")
                    if outc is None or outc == "X":
                        if acc is not False:
                            bad.append((outc, ures, team, n))
                    if acc is True and (n or {}).get("closeStatus") != outc:
                        bad.append((outc, ures, team, n))
                    if outc == "RESOLVED" and ures is True and acc is not False:
                        bad.append((outc, ures, team, n))
        rep.check("CaseCloseValidation invariant :: unknown outcome refused, accepted closeStatus = outcome, RESOLVED refused while a reply is unanswered", not bad, str(bad[:5]))
    return 0 if rep.summary() else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    return offline() if a.offline else live(a.only, a.workers)


if __name__ == "__main__":
    sys.exit(main())
