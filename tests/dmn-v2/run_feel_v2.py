#!/usr/bin/env python3
"""FEEL expression tests for the v2 Part A artefacts: the FEEL is read from process-v2/*.bpmn (never retyped) and evaluated with
`c8ctl feel evaluate` on the cluster engine: PCI scan, reply-subject tag round trip, intake normalisation, investigation preparation, and (part B) the request agent's ledger, hold gate, tool guards, reply merge and late-reply replay check over contexts shaped like the Phase 0 spike findings.
  python3 -I tests/dmn-v2/run_feel_v2.py
Reports to tests/reports/feel-v2.json. Do not run alongside live process runs (token endpoint rate limits).
"""
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from tests.lib import common  # noqa: E402

B = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
Z = "{http://camunda.org/schema/zeebe/1.0}"
V2 = os.path.join(common.ROOT, "process-v2")


def script(bpmn, element):
    root = ET.parse(os.path.join(V2, bpmn)).getroot()
    for el in root.iter():
        if el.get("id") == element:
            return el.find(B + "extensionElements").find(Z + "script").get("expression")
    raise KeyError(element)


def flow_cond(bpmn, flow_id):
    root = ET.parse(os.path.join(V2, bpmn)).getroot()
    for el in root.iter(B + "sequenceFlow"):
        if el.get("id") == flow_id:
            return el.find(B + "conditionExpression").text
    raise KeyError(flow_id)


def tc(i, name, val, interrupted=False, at="2026-10-30T10:00:00Z"):
    """A tool result as in the Phase 0 spike shapes (BUILD-NOTES): normal = object block + elementId; cancelled = text block + interrupted, no elementId."""
    if interrupted:
        return {"id": i, "name": name, "content": [{"type": "text", "text": "Tool execution was canceled."}], "completedAt": at, "interrupted": True}
    return {"id": i, "name": name, "content": [{"type": "object", "content": val}], "elementId": name, "completedAt": at}


def asst(*calls):
    return {"role": "assistant", "toolCalls": [{"id": i, "name": n, "arguments": {}} for i, n in calls]}


def res(*results):
    return {"role": "tool_call_result", "results": list(results)}


def usr_event(text):
    return {"role": "user", "content": [{"type": "object", "content": {"event": "CUSTOMER_REPLY", "replyText": text}}], "metadata": {"timestamp": "2026-10-30T10:02:00Z"}}


PROMPT = {"role": "user", "content": [{"type": "text", "text": "REQUEST ..."}]}
SYSMSG = {"role": "system", "content": [{"type": "text", "text": "sys"}]}
SENT_CVV = {"status": "SENT", "purpose": "CVV_RETRY_ADVICE", "sentAt": "2026-10-30T10:01:00Z", "bodyKey": "120|Dear", "mentorDecision": "APPROVE"}
INV_CVV = {"status": "COMPLETED", "scenario": "INCORRECT_CVV", "recommendedRoute": "INCORRECT_CVV", "decline": {"blockCode": "NONE"}, "cardCheck": {"cardholderName": "X"}, "missingFields": []}


def req_checks(rep):
    """Ledger, hold gate, guards and reply FEEL of HSBC_Decline_Request_Agent over contexts shaped like the Phase 0 spike findings."""
    F = "hsbc-decline-request-agent.bpmn"
    ledger_ids = ["Task_InvLedger", "Task_EmailLedger", "Task_AwaitLedger", "Task_FraudAskLedger", "Task_AwaitFraudLedger", "Task_InterpretLedger", "Task_ReviewLedger", "Task_HandLedger", "Task_CloseLedger"]
    led = {i: script(F, i) for i in ledger_ids}
    rep.check("ledger: the nine tool copies are identical", len(set(led.values())) == 1, "the ledger FEEL differs between tools: %s" % [i for i in ledger_ids if led[i] != led[ledger_ids[0]]])
    L = led[ledger_ids[0]]
    post = script(F, "Task_ExtractLedger")
    src_a = "if is defined(agentContext) and agentContext != null and agentContext.conversation != null then agentContext.conversation.messages else []"
    src_p = "if is defined(agent) and agent != null and agent.context != null and agent.context.conversation != null then agent.context.conversation.messages else []"
    cut = post.replace(src_p, src_a)
    head = cut.split(",\n    audit:")[0]
    rep.check("ledger: post-agent copy = tool copy with agent.context and the audit part only", head + "\n  }\n}.led" == L, "the post-agent ledger differs from the tool ledger beyond source and audit")

    def run(msgs, expr=L, var="agentContext"):
        ctx = {"conversation": {"messages": msgs}}
        return common.feel(expr, {var: ctx} if var == "agentContext" else {"agent": {"context": ctx}})

    # fresh case: only the prompt and the first assistant message
    fresh = [SYSMSG, PROMPT, asst(("a1", "InvestigateCardDecline"))]
    ev_ = lambda cid, msgs, chk, expr=L, var="agentContext": (lambda r: (rep.ok if r["ok"] and chk(r["result"]) else rep.fail)(cid, "" if r["ok"] and chk(r["result"]) else "%s %s" % (r["error"], str(r["result"])[:300])))(run(msgs, expr, var))
    ev_("ledger: fresh case has zero counters and the step call", fresh, lambda x: x["emailsSent"] == 0 and x["investigationsUsed"] == 0 and x["closeAccepted"] is False and [c["name"] for c in x["stepCalls"]] == ["InvestigateCardDecline"] and x["lastEmailStatus"] is None)
    s4 = [SYSMSG, PROMPT, asst(("t1", "InvestigateCardDecline")), res(tc("t1", "InvestigateCardDecline", INV_CVV)),
          asst(("t2", "EmailCustomer")), res(tc("t2", "EmailCustomer", SENT_CVV)), asst(("t3", "AwaitCustomerReply"))]
    ev_("ledger: S4 after the advice email", s4, lambda x: x["emailsSent"] == 1 and x["clarificationsSent"] == 0 and x["investigationsUsed"] == 1 and x["latestScenario"] == "INCORRECT_CVV" and x["resolvingEmailSent"] is True
        and x["lastEmailStatus"] == "SENT" and x["firstSentAt"] == "2026-10-30T10:01:00Z" and x["sentBodyKeys"] == ["120|Dear"] and x["closeAccepted"] is False and x["unansweredReply"] is False)
    cancelled = s4 + [res(tc("t3", "AwaitCustomerReply", None, interrupted=True)), usr_event("Can I use the card now?"), asst(("t4", "EmailCustomer"), ("t5", "CloseCase"))]
    ev_("ledger: cancelled wait is not a result, reply event after the last email is unanswered, current step lists both calls", cancelled,
        lambda x: x["lastAwaitTimedOut"] is False and x["unansweredReply"] is True and x["replyCount"] == 1 and x["lastReplyText"] == "Can I use the card now?" and [c["name"] for c in x["stepCalls"]] == ["EmailCustomer", "CloseCase"])
    answered = cancelled[:-1] + [asst(("t4", "EmailCustomer")), res(tc("t4", "EmailCustomer", {**SENT_CVV, "purpose": "ANSWER_QUESTION", "bodyKey": "200|Dear"}))]
    ev_("ledger: an answer after the reply clears unansweredReply", answered, lambda x: x["unansweredReply"] is False and x["emailsSent"] == 2 and x["sentBodyKeys"] == ["120|Dear", "200|Dear"])
    closed = answered + [asst(("t6", "CloseCase")), res(tc("t6", "CloseCase", {"accepted": True, "closeStatus": "RESOLVED", "reason": "ok"}))]
    ev_("ledger: accepted CloseCase closes the case", closed, lambda x: x["closeAccepted"] is True and x["closeStatus"] == "RESOLVED")
    ev_("ledger: a customer event after the accepted close re-opens it (late reply)", closed + [usr_event("one more thing")], lambda x: x["closeAccepted"] is False and x["unansweredReply"] is True)
    timed = [SYSMSG, PROMPT, asst(("t1", "EmailCustomer")), res(tc("t1", "EmailCustomer", {"status": "SENT", "purpose": "MISSING_CARD_DETAILS", "sentAt": "x", "bodyKey": "k"})),
             asst(("t2", "AwaitCustomerReply")), res(tc("t2", "AwaitCustomerReply", {"status": "TIMED_OUT"}))]
    ev_("ledger: clarification then timed-out wait", timed, lambda x: x["lastAwaitTimedOut"] is True and x["lastEmailWasClarification"] is True and x["clarificationsSent"] == 1 and x["resolvingEmailSent"] is False)
    rework = [SYSMSG, PROMPT, asst(("t1", "EmailCustomer")), res(tc("t1", "EmailCustomer", {"status": "NOT_SENT", "mentorDecision": "REWORK", "purpose": "CVV_RETRY_ADVICE"})),
              asst(("t2", "EmailCustomer")), res(tc("t2", "EmailCustomer", {"status": "NOT_SENT", "mentorDecision": "ESCALATE", "purpose": "CVV_RETRY_ADVICE"}))]
    ev_("ledger: Mentor rework counted, escalation open until HandToTeam returns", rework, lambda x: x["mentorReworks"] == 1 and x["mentorEscalationOpen"] is True and x["emailsSent"] == 0)
    ev_("ledger: HandToTeam closes the escalation and gives the team decision", rework + [asst(("t3", "HandToTeam")), res(tc("t3", "HandToTeam", {"status": "HANDLED", "teamDecision": "RESOLVED_BY_TEAM", "customerUpdate": "u"}))],
        lambda x: x["mentorEscalationOpen"] is False and x["teamDecision"] == "RESOLVED_BY_TEAM" and x["teamInstructions"] == "u")
    fraud = [SYSMSG, PROMPT, asst(("t1", "InvestigateCardDecline")), res(tc("t1", "InvestigateCardDecline", {**INV_CVV, "scenario": "FRAUD_ALERT", "recommendedRoute": "FRAUD_ALERT"})),
             asst(("t2", "AskFraudTeam")), res(tc("t2", "AskFraudTeam", {"status": "SENT", "mode": "INITIAL"})), asst(("t3", "AwaitFraudTeamReply")), res(tc("t3", "AwaitFraudTeamReply", {"status": "TIMED_OUT"}))]
    ev_("ledger: fraud initial sent and the wait timed out (a chase is possible)", fraud, lambda x: x["fraudInitialSent"] is True and x["lastFraudAwaitTimedOut"] is True and x["fraudChasesUsed"] == 0 and x["latestScenario"] == "FRAUD_ALERT")
    fr2 = fraud + [asst(("t4", "AwaitFraudTeamReply")), res(tc("t4", "AwaitFraudTeamReply", {"status": "REPLY_RECEIVED", "replyText": "Block removed."})), asst(("t5", "InterpretFraudReply")),
                   res(tc("t5", "InterpretFraudReply", {"status": "INTERPRETED", "fraudTeamDecision": "UNCLEAR", "needsHumanReview": True, "interpretationConfidence": 0.5})),
                   asst(("t6", "ReviewFraudReply")), res(tc("t6", "ReviewFraudReply", {"status": "REVIEWED", "fraudTeamDecision": "BLOCK_REMOVED"}))]
    ev_("ledger: reply, interpretation needing review, human review decides", fr2, lambda x: x["latestFraudReply"]["replyText"] == "Block removed." and x["needsHumanReview"] is True and x["fraudReviewed"] is True and x["fraudTeamDecision"] == "BLOCK_REMOVED")
    ev_("ledger: a newer fraud reply makes the earlier interpretation stale", fr2 + [asst(("t7", "AwaitFraudTeamReply")), res(tc("t7", "AwaitFraudTeamReply", {"status": "REPLY_RECEIVED", "replyText": "Actually keep it."}))],
        lambda x: x["fraudTeamDecision"] is None and x["latestFraudInterp"] is None and x["fraudReviewed"] is False)
    ev_("ledger: post-agent copy returns the same facts and an ordered audit", closed, lambda x: x["emailsSent"] == 2 and x["closeAccepted"] is True and [a["action"] for a in x["audit"]][:3] == ["INVESTIGATED", "CUSTOMER_EMAIL_SENT", "CUSTOMER_WAIT_CANCELLED"]
        and "REPLY_RECEIVED" in [a["action"] for a in x["audit"]] and x["audit"][-1]["action"] == "CASE_CLOSED" and all((a["details"] or {}).get("cardCheck") is None for a in x["audit"]), expr=post, var="agent")

    # hold gate (Phase 0 spike 4): results of finished tools of the current step are in toolCallResults, not in the context
    pend = script(F, "Task_PendingTools")
    step = [SYSMSG, PROMPT, asst(("h1", "HandToTeam"), ("h2", "AwaitCustomerReply"))]
    r = common.feel(pend, {"agentContext": {"conversation": {"messages": step}}, "toolCallResults": []})
    rep.check("hold gate: both calls pending at the start of the step", r["ok"] and sorted(x["name"] for x in r["result"]) == ["AwaitCustomerReply", "HandToTeam"], "pending %s" % r)
    r = common.feel(pend, {"agentContext": {"conversation": {"messages": step}}, "toolCallResults": [{"id": "h1", "name": "HandToTeam"}]})
    rep.check("hold gate: a finished tool of the step (toolCallResults) is no longer pending", r["ok"] and [x["name"] for x in r["result"]] == ["AwaitCustomerReply"], "pending %s" % r)
    r = common.feel(pend, {"agentContext": {"conversation": {"messages": step[:2] + [asst(("h1", "HandToTeam")), res(tc("h1", "HandToTeam", {"status": "HANDLED"})), asst(("h3", "AwaitFraudTeamReply"))]}}})
    rep.check("hold gate: results already in the context are not pending; no toolCallResults variable is tolerated", r["ok"] and [x["name"] for x in r["result"]] == ["AwaitFraudTeamReply"], "pending %s" % r)
    hold = flow_cond(F, "Flow_HoldWhileBusy_Timer_HoldPoll") if False else None
    root = ET.parse(os.path.join(V2, F)).getroot()
    hold = [c.text for c in root.iter(B + "conditionExpression") if c.text and "holdGate" in c.text][0]
    base = {"holdGate": True, "holdStartedAt": "2099-01-01T00:00:00Z", "replyHoldMax": "PT4H"}
    for cid, pending, chg, want in [("busy tool (user task) holds the event", [{"id": "a", "name": "HandToTeam"}], {}, True),
                                    ("only pure waits release the event", [{"id": "a", "name": "AwaitCustomerReply"}, {"id": "b", "name": "AwaitFraudTeamReply"}], {}, False),
                                    ("nothing pending releases the event", [], {}, False),
                                    ("holdGate=false releases at once", [{"id": "a", "name": "HandToTeam"}], {"holdGate": False}, False),
                                    ("the replyHoldMax bound releases a long hold", [{"id": "a", "name": "HandToTeam"}], {"holdStartedAt": "2000-01-01T00:00:00Z"}, False)]:
        r = common.feel(hold, {**base, **chg, "pending": pending})
        rep.check("hold gate condition: " + cid, r["ok"] and r["result"] is want, "got %s" % r)

    # guards
    gm = script(F, "Task_GuardEmail")
    led0 = {"emailsSent": 0, "sentBodyKeys": ["19|Dear customer, hello"], "stepCalls": [{"id": "x", "name": "EmailCustomer"}]}
    ge = lambda body, purpose="CVV_RETRY_ADVICE", l=led0: common.feel(gm, {"body": body, "purpose": purpose, "ledger": l, "maxCustomerEmails": 5})
    for cid, body, purpose, l, frag in [("clean body passes", "Dear Jasmin,\n\nPlease retry with the card ending 8801 for AED 620.00 on 22/06/2026.\n\nHSBC Commercial Cards Servicing Team", "CVV_RETRY_ADVICE", led0, None),
                                        ("card number in the body is refused (digits with spaces)", "Your card 5550 4100 9901 8801 is fine", "CVV_RETRY_ADVICE", led0, "12 or more digits"),
                                        ("empty body is refused", "  ", "CVV_RETRY_ADVICE", led0, "empty"),
                                        ("unknown purpose is refused (enum values are not enforced by the model API)", "Hello there", "PURPLE", led0, "Unknown purpose"),
                                        ("two EmailCustomer calls in one step: refused", "Hello", "STATUS_UPDATE", {**led0, "stepCalls": [{"id": "x", "name": "EmailCustomer"}, {"id": "y", "name": "EmailCustomer"}]}, "one EmailCustomer"),
                                        ("identical body already sent: refused (idempotency)", "Dear customer, hello", "STATUS_UPDATE", {**led0, "sentBodyKeys": ["20|Dear customer, hello"]}, "identical email")]:
        r = ge(body, purpose, l)
        pre = r["result"]["pre"] if r["ok"] else None
        rep.check("EmailCustomer guard: " + cid, r["ok"] and ((pre is None) if frag is None else (pre is not None and frag in pre)), "got %s" % r)
    r = ge("Dear customer, hello", "STATUS_UPDATE", {**led0, "sentBodyKeys": ["20|Dear customer, hello"]})
    rep.check("EmailCustomer guard: bodyKey is length|first 80 characters, as stored in SENT results", r["ok"] and r["result"]["bodyKey"] == "20|Dear customer, hello", "got %s" % r)
    ga = script(F, "Task_GuardAwait")
    wl = {"closeAccepted": False, "lastEmailStatus": "SENT", "stepCalls": [{"id": "a", "name": "AwaitCustomerReply"}]}
    for cid, phase, l, frag in [("after a SENT email, alone in the step: allowed", "AWAITING_INFO", wl, None), ("last email not sent: refused", "AWAITING_INFO", {**wl, "lastEmailStatus": "NOT_SENT"}, "SENT"),
                                ("with a non-wait tool in the same step: refused", "CONVERSATION_OPEN", {**wl, "stepCalls": [{"id": "a", "name": "AwaitCustomerReply"}, {"id": "b", "name": "EmailCustomer"}]}, "alone"),
                                ("closed case: refused", "AWAITING_INFO", {**wl, "closeAccepted": True}, "closed"), ("unknown phase: refused", "SOON", wl, "phase")]:
        r = common.feel(ga, {"phase": phase, "ledger": l, "customerReplySla": "PT15M", "conversationWindow": "PT20M"})
        pre = r["result"]["pre"] if r["ok"] else None
        rep.check("AwaitCustomerReply guard: " + cid, r["ok"] and ((pre is None) if frag is None else (pre is not None and frag in pre)), "got %s" % r)
    r = common.feel(ga, {"phase": "CONVERSATION_OPEN", "ledger": wl, "customerReplySla": "PT15M", "conversationWindow": "PT20M"})
    rep.check("AwaitCustomerReply guard: timer from the process (conversationWindow), never from the model", r["ok"] and r["result"]["wait"] == "PT20M", "got %s" % r)
    gk = script(F, "Task_GuardAsk")
    fl = {"closeAccepted": False, "latestScenario": "FRAUD_ALERT", "fraudInitialSent": False, "lastFraudAwaitTimedOut": False, "fraudChasesUsed": 0, "stepCalls": [{"id": "a", "name": "AskFraudTeam"}]}
    for cid, mode, l, frag in [("INITIAL for a fraud scenario: allowed", "INITIAL", fl, None), ("not a fraud scenario: refused", "INITIAL", {**fl, "latestScenario": "INCORRECT_CVV"}, "FRAUD_ALERT"),
                               ("second INITIAL: refused", "INITIAL", {**fl, "fraudInitialSent": True}, "already"), ("CHASE before a timed-out wait: refused", "CHASE", {**fl, "fraudInitialSent": True}, "timed out"),
                               ("CHASE after a timeout: allowed", "CHASE", {**fl, "fraudInitialSent": True, "lastFraudAwaitTimedOut": True}, None),
                               ("CHASE over the cap (maxFraudChases from the process): refused", "CHASE", {**fl, "fraudInitialSent": True, "lastFraudAwaitTimedOut": True, "fraudChasesUsed": 1}, "limit")]:
        r = common.feel(gk, {"mode": mode, "note": "n", "ledger": l, "maxFraudChases": 1})
        pre = r["result"]["pre"] if r["ok"] else None
        rep.check("AskFraudTeam guard: " + cid, r["ok"] and ((pre is None) if frag is None else (pre is not None and frag in pre)), "got %s" % r)

    # reply merge, event and late-reply replay check
    mg = script(F, "Task_MergeRequestReply")
    base = {"senderEmail": "jasmin@x.invalid", "effectiveSenderEmail": "jasmin@x.invalid", "demoEmailRedirect": "", "dqmResult": {"authorisedContacts": [{"email": "sara@x.invalid"}]}, "intakeFacts": {"authorisedContacts": []}}
    rp = lambda frm, body: {"fromAddress": frm, "plainTextBody": body, "receivedAt": "2026-10-30T10:00:00Z", "subject": "RE: x", "attachments": []}
    r = common.feel(mg, {**base, "customerReply": rp("Jasmin <JASMIN@x.invalid>", "Can I use the card now?\n\nRegards\n\nOn Thu, 30 Oct 2026, HSBC wrote:\n> old text")})
    rep.check("reply merge: sender verified, quoted history stripped, address normalised", r["ok"] and r["result"]["replySenderVerified"] is True and r["result"]["replyFrom"] == "jasmin@x.invalid" and "old text" not in r["result"]["replyText"], "got %s" % r)
    r = common.feel(mg, {**base, "customerReply": rp("sara@x.invalid", "ok")})
    rep.check("reply merge: a DQM authorised contact is verified", r["ok"] and r["result"]["replySenderVerified"] is True, "got %s" % r)
    r = common.feel(mg, {**base, "customerReply": rp("evil@other.invalid", "pay me")})
    rep.check("reply merge: an unknown address is unverified (content goes to a person)", r["ok"] and r["result"]["replySenderVerified"] is False and r["result"]["replyFromDomain"] == "other.invalid", "got %s" % r)
    r = common.feel(mg, {**base, "demoEmailRedirect": "demo@x.invalid", "customerReply": rp("evil@other.invalid", "x")})
    rep.check("reply merge: demo-redirect mode verifies any sender (as v12)", r["ok"] and r["result"]["replySenderVerified"] is True, "got %s" % r)
    r = common.feel(mg, {**base, "customerReply": rp("jasmin@x.invalid", "x" * 5000)})
    rep.check("reply merge: text truncated to 4,000 characters", r["ok"] and len(r["result"]["replyText"]) == 4000, "got %s" % str(r)[:200])
    be = script(F, "Task_BuildReplyEvent")
    r = common.feel(be, {"replySenderVerified": True, "replyReceivedAt": "t", "replyText": "hi", "replyTranscript": None, "replyAttachmentCount": 0, "replyDocs": [], "requestRef": "HSBC-AGT-1-1", "requestLabel": "card ending 8801", "maskedCardNumber": "XXXX-XXXX-XXXX-8801", "replyFromDomain": "x.invalid"})
    rep.check("event message: verified reply carries text, empty transcript and the tag", r["ok"] and r["result"]["event"] == "CUSTOMER_REPLY" and r["result"]["replyText"] == "hi" and r["result"]["attachmentTranscript"] == "" and r["result"]["inReplyToTag"] == "[HSBC-AGT-1-1]", "got %s" % r)
    r = common.feel(be, {"replySenderVerified": False, "replyReceivedAt": "t", "replyText": "secret", "replyTranscript": None, "replyAttachmentCount": 0, "replyDocs": [], "requestRef": "r", "requestLabel": "l", "maskedCardNumber": "m", "replyFromDomain": "other.invalid"})
    rep.check("event message: unverified reply withholds the content", r["ok"] and r["result"]["event"] == "CUSTOMER_REPLY_UNVERIFIED" and "secret" not in str(r["result"]) and r["result"]["fromDomain"] == "other.invalid", "got %s" % r)
    st = script(F, "Task_CheckLateStale")
    for cid, recv, want in [("a reply received before the close is a replay: ignored", "2026-10-30T10:00:00Z", True), ("a reply after the close is new", "2026-10-30T10:30:00Z", False)]:
        r = common.feel(st, {"customerReply": {"receivedAt": recv}, "closedAt": "2026-10-30T10:15:00Z"})
        rep.check("late reply: " + cid, r["ok"] and r["result"]["stale"] is want, "got %s" % r)


def ev(rep, cid, expr, variables, check):
    r = common.feel(expr, variables)
    if not r["ok"]:
        rep.fail(cid, "evaluation failed: %s" % r["error"])
        return
    ok, why = check(r["result"])
    (rep.ok if ok else rep.fail)(cid, "" if ok else "%s (result %s)" % (why, str(r["result"])[:300]))


def main():
    rep = common.Reporter("feel-v2")
    pci = script("hsbc-customer-communication-agentic.bpmn", "Task_PciScan")
    for body, expect in [("Case ID: HSBC-AGT-20261030170156535-1 and fraud tag [HSBC-AFR-20261030170156535-1] for the card ending 8801", False), ("card 5550 4100 9901 8801", True), ("card 5550-4100-9901-8801", True), ("a 19-digit account 1234567890123456789 here", True),
                         ("line one\n5550410099018801\nline three", True), ("card ending 8801, AED 2,150.00 on 22/06/2026", False),
                         ("call +971 4 123 4567 about the card ending 8801", False), ("Dear Jasmin,\n\nHSBC Commercial Cards Servicing Team", False)]:
        ev(rep, "pci %r" % body[:40], pci, {"communicationDraft": {"body": body}}, lambda x, e=expect: (x["pciViolation"] is e, "pciViolation should be %s" % e))
    ev(rep, "pci null body", pci, {"communicationDraft": {"body": None}}, lambda x: (x["pciViolation"] is False and x["bodyMissing"] is True, "null body is missing, not a violation"))
    ev(rep, "pci blank body", pci, {"communicationDraft": {"body": "   "}}, lambda x: (x["bodyMissing"] is True, "blank body is missing"))

    sub = script("hsbc-customer-communication-agentic.bpmn", "Task_BuildDraftSubject")
    for rtype, want in [("SENDER", "[HSBC-AGT-123-2]"), ("AUTHORISED_CONTACT", "[HSBC-AGT-123-2]"), ("FRAUD_TEAM", "[HSBC-AFR-123-2]")]:
        ev(rep, "subject tag %s" % rtype, sub, {"caseId": "HSBC-AGT-123-2", "recipientType": rtype, "emailSubject": "Declined [HSBC-CARDS-AI]", "modelDraft": {"body": "x"}},
           lambda x, w=want: (x["subject"].endswith(w) and x["subject"].startswith("RE: "), "subject should end with %s" % w))
    ev(rep, "subject: v12 tags never produced", sub, {"caseId": "HSBC-AGT-123-1", "recipientType": "FRAUD_TEAM", "emailSubject": "s", "modelDraft": {"body": "x"}},
       lambda x: ("HSBC-FRD" not in x["subject"] and "HSBC-DCL" not in x["subject"], "must not contain a v12 tag"))
    # tag round trip: the customer and fraud tags map back to the same requestRef (listener key expressions are the agent builder's; the digits must survive)
    rt = common.feel('replace(upper case(subject), ".*\\\\[HSBC-AFR-([0-9]+-[0-9]+)\\\\].*", "HSBC-AGT-$1")', {"subject": "RE: x [HSBC-AFR-20261030123456789-2]"})
    rep.check("fraud tag maps back to requestRef", rt["ok"] and rt["result"] == "HSBC-AGT-20261030123456789-2", "got %s" % rt)

    norm = script("hsbc-email-intake.bpmn", "Task_NormaliseIntake")
    dq = {"status": "FOUND", "clientName": "C", "authorisedContacts": [{"name": "A", "email": "a@x.invalid", "isPrimary": False}, {"name": "P", "email": "p@x.invalid", "isPrimary": True}]}
    base = {"caseId": "CASE", "dqmAttempts": 1, "priorFollowUps": 0, "intakeSender": "P@X.invalid"}
    two = {"requestCount": 2, "splitConfidence": 0.9, "requests": [
        {"cardDigits": "5550 4100 9901 8801", "transactionDate": "2026-06-22", "transactionAmount": 620, "transactionCurrency": "aed", "merchantName": "Emaar Malls"},
        {"cardDigits": "4000 1234 5678 3821", "transactionDate": "2026-06-23", "transactionAmount": "150.00", "merchantName": "Dubai Mall"}]}
    ev(rep, "intake: two cards -> two requests -CASE-1/-2 with masked numbers", norm, {**base, "intakeExtraction": two, "dqmResult": dq},
       lambda x: ([r["requestRef"] for r in x["requests"]] == ["CASE-1", "CASE-2"] and [r["maskedCardNumber"] for r in x["requests"]] == ["XXXX-XXXX-XXXX-8801", "XXXX-XXXX-XXXX-3821"]
                  and x["requestCount"] == 2 and x["senderAuthorised"] is True and x["authorisedContacts"][0]["isPrimary"] is True, "split/mask/sender check"))
    dup = {"requestCount": 3, "requests": two["requests"] + [{"cardDigits": "5550410099018801", "transactionDate": "2026-06-22", "transactionAmount": "620.00", "fromAttachment": True}]}
    ev(rep, "intake: duplicates merged (same last four, date, amount)", norm, {**base, "intakeExtraction": dup, "dqmResult": dq},
       lambda x: (x["requestCount"] == 2 and x["modelRequestCount"] == 3 and x["duplicatesMerged"] == 1, "dedup"))
    ev(rep, "intake: unparsed extraction -> requestCount null", norm, {**base, "intakeExtraction": None, "dqmResult": dq},
       lambda x: (x["requestCount"] is None and x["extractionParsed"] is False, "parse guard"))
    ev(rep, "intake: empty contact list -> senderAuthorised null", norm, {**base, "intakeExtraction": two, "dqmResult": {"status": "FOUND", "authorisedContacts": []}},
       lambda x: (x["senderAuthorised"] is None, "null authorisation"))
    ev(rep, "intake: other sender -> senderAuthorised false", norm, {**base, "intakeSender": "other@x.invalid", "intakeExtraction": two, "dqmResult": dq},
       lambda x: (x["senderAuthorised"] is False, "unauthorised"))
    ev(rep, "intake: no DQM result -> rpaStatus null", norm, {**base, "intakeExtraction": two, "dqmResult": None},
       lambda x: (x["rpaStatus"] is None and x["customerFound"] is None, "no dqm"))
    ev(rep, "intake: a request without identifiers is never merged", norm, {**base, "intakeExtraction": {"requests": [{"cardDigits": None}, {"cardDigits": None}]}, "dqmResult": dq},
       lambda x: (x["requestCount"] == 2, "no merge on empty key"))

    prep = script("hsbc-tool-investigate-card-decline.bpmn", "Task_Prepare")
    dqm = {"clientId": "BKT001", "clientName": "N", "accountNumbers": ["A1"]}
    ev(rep, "investigate prepare: S4 inputs", prep, {"cardNumber": "5550 4100 9901 8801", "transactionDate": "2026-06-22", "transactionAmount": "620.00", "transactionCurrency": "aed", "merchantName": "Emaar Malls", "dqmResult": dqm},
       lambda x: (x["cardDigitsLength"] == 16 and x["cardLastFour"] == "8801" and x["reqAmountText"] == "620.00" and x["refused"] is False and x["dqmAccountNumber"] == "A1", "prepare"))
    ev(rep, "investigate prepare: cap reached -> refused", prep, {"cardNumber": "x", "investigationsUsed": 3, "maxInvestigations": 3}, lambda x: (x["refused"] is True, "cap"))
    ev(rep, "investigate prepare: no inputs at all", prep, {}, lambda x: (x["cardDigitsLength"] == 0 and x["reqDate"] is None and x["reqAmount"] is None and x["refused"] is False, "defaults"))
    req_checks(rep)
    return 0 if rep.summary() else 1


if __name__ == "__main__":
    sys.exit(main())
