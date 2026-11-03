#!/usr/bin/env python3
"""Process tests (playbook s15 layer 6): start the callable sub-processes DIRECTLY and drive them to the end.

  HSBC_Customer_Communication  every purpose through the Mentor user task (APPROVE / REWORK / REJECT / ESCALATE)
  HSBC_Decline_Incorrect_CVV   approve and reject
  HSBC_Decline_Fraud_Alert     up to the fraud-team wait, then `c8ctl publish msg hsbc-fraud-team-response`

Needs the full deployment (all resources, deployed together). Starts instances with `c8ctl create pi`, completes
user tasks with `c8ctl complete ut`, publishes with `c8ctl publish msg`; reads state through the REST API.
Asserts the end state, zero incidents (any state, whole instance tree) and the audit entries.

Safety: every outbound email goes to the demo redirect only (demoEmailRedirect), and the harness refuses to start an
instance whose variables would send anywhere else. Every instance this run creates is cancelled if it is left active.
Only HSBC_* process definitions are touched.

  python3 -I tests/process/run_process.py [--only NAME] [--list] [--parallel 4] [--timeout 360]
"""
import argparse
import atexit
import concurrent.futures as cf
import json
import os
import random
import re
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from tests.lib import common  # noqa: E402
from tests.dmn import cases as dmn_cases  # noqa: E402

REDIRECT = "nikita.tihhomirov@camunda.com"
COMM, CVV, FRAUD = "HSBC_Customer_Communication", "HSBC_Decline_Incorrect_CVV", "HSBC_Decline_Fraud_Alert"
MENTOR, REVIEW, CHASE = "UserTask_MentorApproval", "UserTask_ReviewFraudResponse", "UserTask_ChaseFraudTeam"
TERMINAL = {"COMPLETED", "TERMINATED", "CANCELED", "CANCELLED"}

rest = None
created = []  # root instance keys, cancelled at exit when still active
_lock = threading.Lock()
_counter = [0]


def case_id():
    with _lock:
        _counter[0] += 1
        n = _counter[0]
    return "HSBC-DCL-99%s%02d" % (str(int(time.time() * 1000))[-13:], n % 100)


# ------------------------------------------------------------------------------------------- fixtures
def facts(**over):
    f = {"maskedCardNumber": "XXXX-XXXX-XXXX-8801", "cardLastFour": "8801", "transactionDate": "2026-06-22",
         "transactionAmount": 620.0, "transactionCurrency": "AED", "merchantName": "Example Merchant",
         "companyName": "Example Travel Ltd", "customerName": "Example Travel Ltd",
         "authorisedContacts": [{"name": "Test Contact", "email": "contact@example.com", "role": "Administrator", "isPrimary": True}],
         "missingFields": [], "rpaStatus": "OK", "clientFound": True, "cardFound": True, "senderAuthorised": True}
    f.update(over)
    return f


def base_vars(cid=None, **over):
    v = {"caseId": cid or case_id(), "triageFacts": facts(), "senderEmail": "sender@example.com", "senderName": "Test Sender",
         "emailSubject": "Declined transaction (automated test)", "messageId": "<automated-test@example.com>",
         "fraudTeamEmail": REDIRECT, "mentorSlaDuration": "PT4H", "fraudTeamSlaDuration": "PT24H", "auditTrail": [],
         "demoEmailRedirect": REDIRECT, "reworkCount": 0}
    v.update(over)
    return v


def comm_vars(purpose, **over):
    extra = {"communicationPurpose": purpose}
    if purpose.startswith("FRAUD_OUTCOME"):
        extra["fraudTeamSummary"] = "Fraud team reply (automated test): " + ("block removed" if "REMOVED" in purpose else "keep the block and reissue")
    if purpose == "REQUEST_COMPLETE_DETAILS":
        extra["notFoundGuidance"] = "Ask for the complete set of details."
        extra["clarifyingQuestions"] = ["Please send the full 16-digit card number."]
    if purpose == "MISSING_REQUIRED_DATA":
        extra["missingFields"] = ["transactionDate"]
    extra.update(over)
    return base_vars(**extra)


def evidence(code, block):
    return {"status": "FOUND", "recordFound": True, "reasonCode": code[:4], "reasonCodeRaw": code, "blockCode": block,
            "evidence": {"pagesVisited": ["Home", "Card search", "Decline detail"], "capturedAt": "2026-10-29T10:00:00Z"}}


# ------------------------------------------------------------------------------------------- engine access
def create_pi(pid, variables):
    assert variables.get("demoEmailRedirect") == REDIRECT, "refusing to start without the demo email redirect"
    assert variables.get("fraudTeamEmail") in (REDIRECT, None), "refusing: fraud team email must be the redirect"
    rc, vals, raw = common.c8("create", "pi", "--id", pid, "--variables", json.dumps(variables))
    key = None
    for v in vals:
        if isinstance(v, dict):
            for k, x in v.items():
                if k.lower().replace("_", "") in ("processinstancekey", "key"):
                    key = str(x)
    if rc != 0 or not key:
        raise RuntimeError("create pi failed (rc=%s): %s" % (rc, raw[:300]))
    with _lock:
        created.append(key)
    return key


def cancel_pi(key):
    common.c8("cancel", "pi", key)


def cleanup():
    for k in list(created):
        code, out = rest.get("/v2/process-instances/%s" % k)
        if code == 200 and out.get("state") == "ACTIVE":
            cancel_pi(k)
            print("cancelled leftover instance %s" % k)


def state(key):
    code, out = rest.get("/v2/process-instances/%s" % key)
    return out.get("state") if code == 200 else None


def tree(key):
    keys, todo = [key], [key]
    while todo:
        k = todo.pop()
        for i in rest.search("process-instances", {"parentProcessInstanceKey": k}, 200):
            keys.append(str(i["processInstanceKey"]))
            todo.append(str(i["processInstanceKey"]))
    return keys


def var(pi_key, name):
    """Value of a variable at the instance's own scope (full value)."""
    items = rest.search("variables", {"processInstanceKey": str(pi_key), "name": name}, 20)
    items = [i for i in items if str(i.get("scopeKey")) == str(pi_key)] or items
    if not items:
        return None
    it = items[0]
    val = it.get("value")
    if it.get("isTruncated"):
        code, full = rest.get("/v2/variables/%s" % it["variableKey"])
        val = full.get("value", val) if code == 200 else val
    try:
        return json.loads(val)
    except (TypeError, ValueError):
        return val


def reached(keys):
    seen = set()
    for k in keys:
        for i in rest.search("element-instances", {"processInstanceKey": k}, 1000):
            seen.add(i["elementId"])
    return seen


def active_element(keys, element_id):
    return any(rest.search("element-instances", {"processInstanceKey": k, "elementId": element_id, "state": "ACTIVE"}, 5) for k in keys)


def incidents(keys):
    out = []
    for k in keys:
        out += rest.search("incidents", {"processInstanceKey": k}, 100)
    return out


def user_tasks(keys):
    out = []
    for k in keys:
        out += rest.search("user-tasks", {"processInstanceKey": k, "state": "CREATED"}, 50)
    return out


# ------------------------------------------------------------------------------------------- scenario driver
def mentor(decision, comments="Automated test decision"):
    def f(task):
        draft = var(task["processInstanceKey"], "communicationDraft") or {}
        cid = var(task["processInstanceKey"], "caseId") or "HSBC-DCL-0"
        return {"decision": decision, "comments": comments,
                "approvedSubject": draft.get("subject") or "RE: automated test [%s]" % cid,
                "approvedBody": draft.get("body") or "Automated test body. Please ignore.",
                "mentorName": "Automated Test"}
    return f


class Scenario:
    def __init__(self, name, process, variables, tasks=None, messages=None, expect=None, timeout=None, after=None):
        self.name, self.process, self.variables = name, process, variables
        self.tasks = {k: list(v) for k, v in (tasks or {}).items()}    # elementId -> [callable(task) -> vars | vars]
        self.messages = messages or {}                                  # elementId active -> (name, correlationKey, vars)
        self.expect, self.timeout = expect or {}, timeout
        self.after = after or {}   # message element -> user-task element that must have been completed first


def run_scenario(sc, default_timeout):
    out = []
    notes = []
    key = None
    try:
        key = create_pi(sc.process, sc.variables)
        deadline = time.time() + (sc.timeout or default_timeout)
        done_tasks, sent, done_elements = set(), set(), set()
        st = "ACTIVE"
        while time.time() < deadline:
            st = state(key)
            keys = tree(key)
            if st in TERMINAL:
                break
            inc = [i for i in incidents(keys) if i.get("state") in (None, "ACTIVE", "PENDING")]
            if inc:
                break
            for t in user_tasks(keys):
                tk = str(t["userTaskKey"])
                if tk in done_tasks:
                    continue
                queue = sc.tasks.get(t["elementId"])
                if not queue:
                    out.append(("FAIL", "unexpected user task %s (no plan for it)" % t["elementId"]))
                    done_tasks.add(tk)
                    continue
                step = queue.pop(0)
                v = step(t) if callable(step) else step
                rc, _vals, raw = common.c8("complete", "ut", tk, "--variables", json.dumps(v))
                done_tasks.add(tk)
                done_elements.add(t["elementId"])
                if rc != 0:
                    out.append(("FAIL", "complete ut %s failed: %s" % (t["elementId"], raw.strip()[:200])))
            for el, (name, ck, mv) in sc.messages.items():
                if el not in sent and (sc.after.get(el) in (None, *done_elements)) and active_element(keys, el):
                    rc, _v, raw = common.c8("publish", "msg", name, "--correlationKey", ck, "--variables", json.dumps(mv), "--timeToLive", "120000")
                    sent.add(el)
                    out.append(("PASS", "published %s while %s was active" % (name, el)) if rc == 0 else ("FAIL", "publish failed: " + raw.strip()[:200]))
            time.sleep(3)
        st = state(key)
        keys = tree(key)
        if st != "COMPLETED":
            inc = incidents(keys)
            out.append(("FAIL", "instance did not complete: state=%s after %ss; incidents=%s; open tasks=%s; unused plan=%s" % (
                st, int(time.time() - (deadline - (sc.timeout or default_timeout))),
                [(i.get("elementId"), i.get("errorType"), (i.get("errorMessage") or "")[:120]) for i in inc][:3],
                [t["elementId"] for t in user_tasks(keys)], {k: len(v) for k, v in sc.tasks.items() if v})))
        else:
            out.append(("PASS", "state COMPLETED"))
        all_inc = incidents(keys)
        out.append(("FAIL", "incidents: %s" % [(i.get("elementId"), i.get("errorType"), (i.get("errorMessage") or "")[:160]) for i in all_inc][:4]) if all_inc else ("PASS", "no incidents"))
        seen = reached(keys)
        for el in sc.expect.get("reached", []):
            out.append(("PASS", "reached %s" % el) if el in seen else ("FAIL", "never reached %s (reached: %s)" % (el, sorted(seen)[-6:])))
        for el in sc.expect.get("not_reached", []):
            out.append(("PASS", "did not reach %s" % el) if el not in seen else ("FAIL", "unexpectedly reached %s" % el))
        for el in sc.expect.get("optional", []):
            notes.append("%s %s" % (el, "reached" if el in seen else "not reached"))
        if st == "COMPLETED":
            for name, want in sc.expect.get("vars", {}).items():
                got = var(key, name)
                out.append(("PASS", "%s = %s" % (name, json.dumps(got)[:60])) if common.match(want, got) else ("FAIL", "%s is %s, expected %s" % (name, json.dumps(got)[:120], json.dumps(want))))
            audit = var(key, "auditTrail") or []
            actions = [a.get("action") if isinstance(a, dict) else a for a in audit]
            for action, n in sc.expect.get("audit", {}).items():
                c = actions.count(action)
                out.append(("PASS", "audit %s x%d" % (action, c)) if c >= n else ("FAIL", "audit %s x%d, expected >= %d (trail: %s)" % (action, c, n, actions)))
            for action, frag in sc.expect.get("audit_detail", {}).items():
                hit = [a for a in audit if isinstance(a, dict) and a.get("action") == action and frag in json.dumps(a.get("details"))]
                out.append(("PASS", "audit %s mentions %r" % (action, frag)) if hit else ("FAIL", "no %s audit entry containing %r" % (action, frag)))
            for action in sc.expect.get("audit_absent", []):
                out.append(("FAIL", "audit has unexpected %s" % action) if action in actions else ("PASS", "audit has no %s" % action))
        left = {k: len(v) for k, v in sc.tasks.items() if v and k not in sc.expect.get("optional_tasks", [])}
        if st == "COMPLETED" and left:
            out.append(("FAIL", "planned user-task steps never happened: %s" % left))
    except Exception as e:  # noqa: BLE001
        out.append(("FAIL", "harness error: %r" % (e,)))
    finally:
        if key and state(key) == "ACTIVE":
            cancel_pi(key)
            notes.append("cancelled leftover instance")
    return key, out, notes


# ------------------------------------------------------------------------------------------- scenario catalogue
def build():
    S = []
    crt = {r[1]["communicationPurpose"]: r[2] for r in dmn_cases.CUSTOMER_RESPONSE_TYPE if r[3] <= 10}
    for purpose, exp in crt.items():
        needs_mentor = exp["requiresMentorApproval"]
        S.append(Scenario(
            "comm/%s/APPROVE" % purpose, COMM, comm_vars(purpose),
            tasks={MENTOR: [mentor("APPROVE", "Approved by automated test")]},
            expect={"reached": ["End_Sent"] + ([MENTOR] if needs_mentor else []), "not_reached": ["End_Escalated", "End_Cancelled", "End_UnsupportedPurpose"],
                    "optional": [] if needs_mentor else [MENTOR], "optional_tasks": [] if needs_mentor else [MENTOR],
                    "vars": {"communicationSent": True, "communicationOutcome": "SENT", "caseStatus": exp["caseStatusAfterSend"]},
                    "audit": {"COMMUNICATION_SENT": 1}, "audit_detail": {"COMMUNICATION_SENT": REDIRECT}}))
    S.append(Scenario("comm/UNSUPPORTED_PURPOSE", COMM, comm_vars("NOT_A_REAL_PURPOSE"),
                      expect={"reached": ["End_UnsupportedPurpose"], "not_reached": ["End_Sent", MENTOR, "Task_SendEmail"],
                              "vars": {"communicationSent": False, "communicationOutcome": "ESCALATED", "caseStatus": "ESCALATED"},
                              "audit": {"COMMUNICATION_UNSUPPORTED_PURPOSE": 1}, "audit_absent": ["COMMUNICATION_SENT"]}))
    S.append(Scenario("comm/MISSING_CARD_DETAILS/REWORK_then_APPROVE", COMM, comm_vars("MISSING_CARD_DETAILS"),
                      tasks={MENTOR: [mentor("REWORK", "Please make it shorter"), mentor("APPROVE")]},
                      expect={"reached": ["Task_IncrementRework", "End_Sent"], "vars": {"reworkCount": 1, "communicationOutcome": "SENT"},
                              "audit": {"MENTOR_REWORK_REQUESTED": 1, "COMMUNICATION_SENT": 1}}))
    S.append(Scenario("comm/MISSING_CARD_DETAILS/REWORK_budget_exhausted", COMM, comm_vars("MISSING_CARD_DETAILS", reworkCount=3),
                      tasks={MENTOR: [mentor("REWORK", "Still not right")]},
                      expect={"reached": ["End_Escalated"], "not_reached": ["End_Sent", "Task_SendEmail"],
                              "vars": {"communicationSent": False, "communicationOutcome": "ESCALATED", "caseStatus": "ESCALATED"},
                              "audit": {"COMMUNICATION_ESCALATED": 1}, "audit_absent": ["COMMUNICATION_SENT"]}))
    S.append(Scenario("comm/MISSING_CARD_DETAILS/REJECT", COMM, comm_vars("MISSING_CARD_DETAILS"),
                      tasks={MENTOR: [mentor("REJECT", "Do not send")]},
                      expect={"reached": ["End_Cancelled"], "not_reached": ["End_Sent", "Task_SendEmail"],
                              "vars": {"communicationSent": False, "communicationOutcome": "CANCELLED", "caseStatus": "ESCALATED"},
                              "audit": {"COMMUNICATION_CANCELLED": 1}, "audit_absent": ["COMMUNICATION_SENT"]}))
    S.append(Scenario("comm/MISSING_CARD_DETAILS/ESCALATE", COMM, comm_vars("MISSING_CARD_DETAILS"),
                      tasks={MENTOR: [mentor("ESCALATE", "Needs a person")]},
                      expect={"reached": ["End_Escalated"], "not_reached": ["End_Sent", "Task_SendEmail"],
                              "vars": {"communicationSent": False, "communicationOutcome": "ESCALATED"},
                              "audit": {"COMMUNICATION_ESCALATED": 1}, "audit_absent": ["COMMUNICATION_SENT"]}))
    S.append(Scenario("comm/MENTOR_SLA_flag", COMM, comm_vars("MISSING_CARD_DETAILS", mentorSlaDuration="PT20S"),
                      tasks={MENTOR: [lambda t: (time.sleep(40), mentor("APPROVE")(t))[1]]},
                      expect={"reached": ["Timer_MentorSla", "Task_FlagMentorSlaBreach", "End_Sent"], "audit": {"MENTOR_SLA_AT_RISK": 1, "COMMUNICATION_SENT": 1}}))
    # CVV
    S.append(Scenario("cvv/APPROVE", CVV, base_vars(echampsResult=evidence("0076 - INV CVV", "NONE")),
                      tasks={MENTOR: [mentor("APPROVE")]},
                      expect={"reached": ["Task_RecordCvvEvidence", "CallActivity_CvvAdvice", "End_CvvHandled"],
                              "vars": {"caseStatus": "RESOLVED", "communicationSent": True, "communicationOutcome": "SENT"},
                              "audit": {"CVV_EVIDENCE_RECORDED": 1, "COMMUNICATION_SENT": 1}, "audit_detail": {"COMMUNICATION_SENT": REDIRECT}}))
    S.append(Scenario("cvv/REJECT", CVV, base_vars(echampsResult=evidence("0076 - INV CVV", "NONE")),
                      tasks={MENTOR: [mentor("REJECT", "Do not send")]},
                      expect={"reached": ["End_CvvHandled"], "vars": {"caseStatus": "ESCALATED", "communicationSent": False, "communicationOutcome": "CANCELLED"},
                              "audit": {"CVV_EVIDENCE_RECORDED": 1, "COMMUNICATION_CANCELLED": 1}, "audit_absent": ["COMMUNICATION_SENT"]}))
    # Fraud
    def fraud(name, reply, decision, tasks=None, after=None, expect_more=None, **vover):
        cid = case_id()
        v = base_vars(cid=cid, echampsResult=evidence("0713 - FALC DECL", "FRAUD_BLOCK"), **vover)
        exp = {"reached": ["Task_RecordFraudEvidence", "CallActivity_NotifyFraudTeam", "Catch_FraudTeamResponse", "Task_InterpretFraudReply",
                           "BRT_FraudManagementOutcome", "CallActivity_FraudOutcomeToCustomer", MENTOR, "End_FraudCaseHandled"],
               "vars": {"fraudTeamDecision": decision, "caseStatus": "RESOLVED", "communicationSent": True},
               "audit": {"FRAUD_EVIDENCE_RECORDED": 1, "COMMUNICATION_SENT": 2}, "optional": [REVIEW], "optional_tasks": [REVIEW, MENTOR]}
        for k, val in (expect_more or {}).items():
            if isinstance(val, dict):
                exp.setdefault(k, {}).update(val)
            else:
                exp[k] = exp.get(k, []) + val
        t = {MENTOR: [mentor("APPROVE"), mentor("APPROVE")], REVIEW: [{"fraudTeamDecision": decision, "fraudReviewNotes": "Automated test review"}]}
        t.update(tasks or {})
        return Scenario(name, FRAUD, v, tasks=t, expect=exp, after=after,
                        messages={"Gateway_AwaitFraudTeam": ("hsbc-fraud-team-response", cid, {"fraudTeamReply": reply})})
    S.append(fraud("fraud/BLOCK_REMOVED", "Hello, we have reviewed the case. The block has been removed and the card can be used again. Regards, Fraud Team",
                   "BLOCK_REMOVED"))
    S.append(fraud("fraud/KEEP_BLOCK_REISSUE", "Hello, the merchant is flagged for repeated fraud alerts. The card must stay blocked and a replacement card should be issued. Regards, Fraud Team",
                   "KEEP_BLOCK_REISSUE"))
    S.append(fraud("fraud/AMBIGUOUS_reply_human_review", "Thanks for the note. We are still looking into this one and will come back to you.",
                   "KEEP_BLOCK_REISSUE", tasks={REVIEW: [{"fraudTeamDecision": "KEEP_BLOCK_REISSUE", "fraudReviewNotes": "Automated test review"}]},
                   expect_more={"reached": [REVIEW], "audit": {"FRAUD_REPLY_REVIEWED": 1}}))
    S.append(fraud("fraud/CHASE_then_reply", "The block has been removed. The card is fine to use. Fraud Team", "BLOCK_REMOVED",
                   tasks={CHASE: [{"chaseNotes": "Chased the fraud team by phone (automated test)"}]}, after={"Gateway_AwaitFraudTeam": CHASE},
                   fraudTeamSlaDuration="PT20S",
                   expect_more={"reached": ["Timer_FraudTeamSla", CHASE], "audit": {"FRAUD_TEAM_CHASED": 1}}))
    return S


def main():
    global rest
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="substring of a scenario name")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=360, help="seconds per scenario")
    args = ap.parse_args()
    scenarios = [s for s in build() if not args.only or args.only in s.name]
    if args.list:
        for s in scenarios:
            print(s.name)
        return 0
    rest = common.Rest()
    atexit.register(cleanup)
    rep = common.Reporter("process")
    print("running %d scenarios (parallel=%d)" % (len(scenarios), args.parallel))
    with cf.ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futs = {pool.submit(run_scenario, s, args.timeout): s for s in scenarios}
        for f, s in futs.items():
            key, rows, notes = f.result()
            for status, msg in rows:
                if status == "PASS":
                    rep.ok("%s :: %s" % (s.name, msg))
                else:
                    rep.fail("%s (pi %s)" % (s.name, key), msg)
            for n in notes:
                rep.warn("%s :: note" % s.name, n)
    cleanup()
    ok = rep.summary()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
