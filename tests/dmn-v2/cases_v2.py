"""DMN case tables for the v2 agentic build (process-v2/dmn). Same shape as tests/dmn/cases.py:
each case is (name, variables, expected output subset, expected rule index (1-based position in the table)).
Only the NEW and CHANGED decisions are covered here; the four unchanged v12 DMNs (DeclineReasonToScenario, RequiredTriageFields,
RecordNotFoundAction, FraudManagementOutcome) are byte-identical copies and stay covered by tests/dmn/cases.py.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from tests.dmn import cases as v12  # noqa: E402

# ------------------------------------------------------------------ IntakeRouting
IR_BASE = {"extractionParsed": True, "rpaStatus": "OK", "customerFound": True, "notFoundReason": None, "senderAuthorised": True,
           "requestCount": 1, "splitConfidence": 0.95, "maxRequestsPerEmail": 5, "multiRequestMode": "ESCALATE"}


def ir(name, over, route, rule):
    return (name, {**IR_BASE, **over}, {"intakeRoute": route}, rule)


INTAKE_ROUTING = [
    ir("r1 rpaStatus ERROR", {"rpaStatus": "ERROR"}, "RPA_FAILURE_ESCALATION", 1),
    ir("r1 rpaStatus null", {"rpaStatus": None}, "RPA_FAILURE_ESCALATION", 1),
    ir("r1 beats everything", {"rpaStatus": "ERROR", "customerFound": False, "senderAuthorised": False, "requestCount": 0}, "RPA_FAILURE_ESCALATION", 1),
    ir("r2 customer not found", {"customerFound": False, "senderAuthorised": None, "notFoundReason": "CUSTOMER_NOT_FOUND"}, "RECORD_NOT_FOUND", 2),
    ir("r2 beats unauthorised", {"customerFound": False, "senderAuthorised": False}, "RECORD_NOT_FOUND", 2),
    ir("r3 customerFound null", {"customerFound": None, "senderAuthorised": None}, "UNCLASSIFIED_ESCALATION", 3),
    ir("r4 senderAuthorised null (no contact list)", {"senderAuthorised": None}, "UNCLASSIFIED_ESCALATION", 4),
    ir("r5 unauthorised sender", {"senderAuthorised": False}, "UNAUTHORISED_SENDER", 5),
    ir("r5 unauthorised beats unparsed extraction", {"senderAuthorised": False, "extractionParsed": False, "requestCount": None}, "UNAUTHORISED_SENDER", 5),
    ir("r5 unauthorised beats several requests", {"senderAuthorised": False, "requestCount": 3, "multiRequestMode": "SPLIT"}, "UNAUTHORISED_SENDER", 5),
    ir("r6 extraction not parsed", {"extractionParsed": False, "requestCount": None}, "UNCLASSIFIED_ESCALATION", 6),
    ir("r6 extractionParsed null", {"extractionParsed": None}, "UNCLASSIFIED_ESCALATION", 6),
    ir("r7 requestCount null", {"requestCount": None}, "UNCLASSIFIED_ESCALATION", 7),
    ir("r7 requestCount negative", {"requestCount": -1}, "UNCLASSIFIED_ESCALATION", 7),
    ir("r8 no request in the email", {"requestCount": 0}, "OUT_OF_SCOPE_ESCALATION", 8),
    ir("r9 two requests, ESCALATE", {"requestCount": 2}, "UNCLASSIFIED_ESCALATION", 9),
    ir("r9 two requests, mode null", {"requestCount": 2, "multiRequestMode": None}, "UNCLASSIFIED_ESCALATION", 9),
    ir("r9 two requests, unknown mode", {"requestCount": 2, "multiRequestMode": "BOGUS"}, "UNCLASSIFIED_ESCALATION", 9),
    ir("r9 five requests, ESCALATE (cap not reached, mode decides)", {"requestCount": 5}, "UNCLASSIFIED_ESCALATION", 9),
    ir("r10 SPLIT, more than the cap", {"requestCount": 6, "multiRequestMode": "SPLIT"}, "SPLIT_REVIEW", 10),
    ir("r11 SPLIT, low confidence", {"requestCount": 2, "multiRequestMode": "SPLIT", "splitConfidence": 0.6}, "SPLIT_REVIEW", 11),
    ir("r11 SPLIT, null confidence", {"requestCount": 2, "multiRequestMode": "SPLIT", "splitConfidence": None}, "SPLIT_REVIEW", 11),
    ir("r12 SPLIT, two requests, confident", {"requestCount": 2, "multiRequestMode": "SPLIT", "splitConfidence": 0.9}, "PER_REQUEST_JOURNEYS", 12),
    ir("r12 SPLIT, confidence exactly 0.7", {"requestCount": 2, "multiRequestMode": "SPLIT", "splitConfidence": 0.7}, "PER_REQUEST_JOURNEYS", 12),
    ir("r12 SPLIT, exactly the cap", {"requestCount": 5, "multiRequestMode": "SPLIT"}, "PER_REQUEST_JOURNEYS", 12),
    ir("r12 single request", {}, "PER_REQUEST_JOURNEYS", 12),
    ir("r12 single request, null splitConfidence (deviation from design row 8)", {"splitConfidence": None}, "PER_REQUEST_JOURNEYS", 12),
    ir("r12 single request, low splitConfidence (deviation from design row 8)", {"splitConfidence": 0.3}, "PER_REQUEST_JOURNEYS", 12),
]

# ------------------------------------------------------------------ CustomerEmailPolicy
CEP_BASE = {"purpose": "CVV_RETRY_ADVICE", "closeAccepted": False, "mentorEscalationOpen": False, "emailsSent": 0, "maxCustomerEmails": 5,
            "clarificationsSent": 0, "maxClarifications": 2, "mentorReworks": 0, "maxMentorReworks": 3, "latestScenario": "INCORRECT_CVV",
            "latestRecommendedRoute": "INCORRECT_CVV", "fraudTeamDecision": None, "needsHumanReview": None, "fraudReviewed": None, "teamDecision": None}


def cep(name, over, allowed, rule, purpose="@same", reason=None):
    exp = {"allowed": allowed}
    if allowed:
        exp["communicationPurpose"] = {**CEP_BASE, **over}["purpose"] if purpose == "@same" else purpose
    if reason:
        exp["refusedReason"] = {"$contains": reason}
    return (name, {**CEP_BASE, **over}, exp, rule)


def clar(p, route=None):
    return {"purpose": p, "latestRecommendedRoute": route if route else p, "latestScenario": None}


EMAIL_POLICY = [
    cep("r1 case already closed", {"closeAccepted": True}, False, 1, reason="already closed"),
    cep("r1 beats the escalation guard", {"closeAccepted": True, "mentorEscalationOpen": True, "emailsSent": None}, False, 1),
    cep("r2 Mentor escalation open", {"mentorEscalationOpen": True}, False, 2, reason="HandToTeam"),
    cep("r3 emailsSent null", {"emailsSent": None}, False, 3, reason="count could not be determined"),
    cep("r4 mentorReworks null", {"mentorReworks": None}, False, 4, reason="rework count"),
    cep("r5 email cap reached", {"emailsSent": 5}, False, 5, reason="limit of customer emails"),
    cep("r5 email cap beats a status update", {"purpose": "STATUS_UPDATE", "emailsSent": 5}, False, 5),
    cep("one below the email cap is allowed", {"emailsSent": 4}, True, 15),
    cep("r6 rework cap reached", {"mentorReworks": 3}, False, 6, reason="Mentor reworks"),
    cep("r7 clarificationsSent null", {**clar("MISSING_CARD_DETAILS"), "clarificationsSent": None}, False, 7),
    cep("r8 clarification cap reached", {**clar("MISSING_CARD_DETAILS"), "clarificationsSent": 2}, False, 8, reason="clarification limit"),
    cep("r8 cap applies to every clarification purpose", {**clar("CARD_COMPANY_MISMATCH"), "clarificationsSent": 3}, False, 8),
    cep("r9 MISSING_CARD_DETAILS matches route", {**clar("MISSING_CARD_DETAILS")}, True, 9),
    cep("r10 INVALID_CARD_NUMBER matches route", {**clar("INVALID_CARD_NUMBER")}, True, 10),
    cep("r11 MISSING_REQUIRED_DATA matches route", {**clar("MISSING_REQUIRED_DATA")}, True, 11),
    cep("r12 CARD_COMPANY_MISMATCH matches route", {**clar("CARD_COMPANY_MISMATCH")}, True, 12),
    cep("r13 REQUEST_COMPLETE_DETAILS matches route", {**clar("REQUEST_COMPLETE_DETAILS")}, True, 13),
    cep("r14 no investigation yet, missing card", {**clar("MISSING_CARD_DETAILS", None), "latestRecommendedRoute": None}, True, 14),
    cep("r14 no investigation yet, invalid card", {**clar("INVALID_CARD_NUMBER", None), "latestRecommendedRoute": None}, True, 14),
    cep("r14 no investigation yet, missing data", {**clar("MISSING_REQUIRED_DATA", None), "latestRecommendedRoute": None}, True, 14),
    cep("no investigation yet: CARD_COMPANY_MISMATCH is not allowed", {**clar("CARD_COMPANY_MISMATCH", None), "latestRecommendedRoute": None}, False, 22),
    cep("clarification purpose that does not match the route", {**clar("MISSING_CARD_DETAILS", "INVALID_CARD_NUMBER")}, False, 22, reason="does not match"),
    cep("clarification purpose when the route is a CVV decline", {"purpose": "REQUEST_COMPLETE_DETAILS", "latestRecommendedRoute": "INCORRECT_CVV"}, False, 22),
    cep("r15 CVV advice after an incorrect-CVV decline", {}, True, 15),
    cep("CVV advice when the scenario is fraud", {"latestScenario": "FRAUD_ALERT"}, False, 22),
    cep("CVV advice before any investigation", {"latestScenario": None, "latestRecommendedRoute": None}, False, 22),
    cep("r16 block removed, no review pending", {"purpose": "FRAUD_OUTCOME_BLOCK_REMOVED", "fraudTeamDecision": "BLOCK_REMOVED", "needsHumanReview": False}, True, 16),
    cep("r17 block removed after review", {"purpose": "FRAUD_OUTCOME_BLOCK_REMOVED", "fraudTeamDecision": "BLOCK_REMOVED", "needsHumanReview": True, "fraudReviewed": True}, True, 17),
    cep("r18 block stays, no review pending", {"purpose": "FRAUD_OUTCOME_KEEP_BLOCK", "fraudTeamDecision": "KEEP_BLOCK_REISSUE", "needsHumanReview": False}, True, 18),
    cep("r19 block stays after review", {"purpose": "FRAUD_OUTCOME_KEEP_BLOCK", "fraudTeamDecision": "KEEP_BLOCK_REISSUE", "needsHumanReview": True, "fraudReviewed": True}, True, 19),
    cep("fraud outcome while review is pending and not done", {"purpose": "FRAUD_OUTCOME_BLOCK_REMOVED", "fraudTeamDecision": "BLOCK_REMOVED", "needsHumanReview": True, "fraudReviewed": False}, False, 22),
    cep("fraud outcome with unknown review state", {"purpose": "FRAUD_OUTCOME_KEEP_BLOCK", "fraudTeamDecision": "KEEP_BLOCK_REISSUE", "needsHumanReview": None, "fraudReviewed": None}, False, 22),
    cep("block-removed email when the fraud team kept the block", {"purpose": "FRAUD_OUTCOME_BLOCK_REMOVED", "fraudTeamDecision": "KEEP_BLOCK_REISSUE", "needsHumanReview": False}, False, 22),
    cep("block-stays email when the fraud team removed the block", {"purpose": "FRAUD_OUTCOME_KEEP_BLOCK", "fraudTeamDecision": "BLOCK_REMOVED", "needsHumanReview": False}, False, 22),
    cep("fraud outcome with no fraud decision", {"purpose": "FRAUD_OUTCOME_BLOCK_REMOVED", "fraudTeamDecision": None, "needsHumanReview": False}, False, 22),
    cep("r20 hand-over update after a team decision", {"purpose": "HUMAN_ACTION_UPDATE", "teamDecision": "RESOLVED_BY_TEAM"}, True, 20),
    cep("hand-over update without a team decision", {"purpose": "HUMAN_ACTION_UPDATE", "teamDecision": None}, False, 22),
    cep("r21 status update", {"purpose": "STATUS_UPDATE"}, True, 21),
    cep("r21 answer to a question", {"purpose": "ANSWER_QUESTION"}, True, 21),
    cep("r22 unknown purpose", {"purpose": "SOMETHING_ELSE"}, False, 22),
    cep("r22 null purpose", {"purpose": None}, False, 22),
    cep("r22 lower-case purpose", {"purpose": "status_update"}, False, 22),
    cep("r22 UNAUTHORISED_SENDER is not an agent purpose", {"purpose": "UNAUTHORISED_SENDER"}, False, 22),
]

# ------------------------------------------------------------------ CaseCloseValidation
CCV_BASE = {"outcome": "RESOLVED", "resolvingEmailSent": True, "lastAwaitTimedOut": False, "lastEmailWasClarification": False,
            "latestScenario": "INCORRECT_CVV", "teamDecision": None, "unansweredReply": False}


def ccv(name, over, accepted, status, rule):
    exp = {"accepted": accepted}
    if status:
        exp["closeStatus"] = status
    return (name, {**CCV_BASE, **over}, exp, rule)


CASE_CLOSE = [
    ccv("r1 RESOLVED with an unanswered reply", {"unansweredReply": True}, False, None, 1),
    ccv("r1 beats a resolving email", {"unansweredReply": True, "resolvingEmailSent": True, "teamDecision": "RESOLVED_BY_TEAM"}, False, None, 1),
    ccv("r2 RESOLVED after a sent resolving email", {}, True, "RESOLVED", 2),
    ccv("r2 unansweredReply null counts as none", {"unansweredReply": None}, True, "RESOLVED", 2),
    ccv("r3 RESOLVED by the team", {"resolvingEmailSent": False, "teamDecision": "RESOLVED_BY_TEAM"}, True, "RESOLVED", 3),
    ccv("r3 resolvingEmailSent null, team resolved", {"resolvingEmailSent": None, "teamDecision": "RESOLVED_BY_TEAM"}, True, "RESOLVED", 3),
    ccv("r4 RESOLVED with no evidence", {"resolvingEmailSent": False}, False, None, 4),
    ccv("r4 RESOLVED, team returned to agent", {"resolvingEmailSent": False, "teamDecision": "RETURN_TO_AGENT"}, False, None, 4),
    ccv("r4 RESOLVED, facts absent", {"resolvingEmailSent": None}, False, None, 4),
    ccv("r5 CLOSED_NO_RESPONSE after a timed-out clarification", {"outcome": "CLOSED_NO_RESPONSE", "lastEmailWasClarification": True, "lastAwaitTimedOut": True}, True, "CLOSED_NO_RESPONSE", 5),
    ccv("r6 CLOSED_NO_RESPONSE, last email was not a clarification", {"outcome": "CLOSED_NO_RESPONSE", "lastEmailWasClarification": False, "lastAwaitTimedOut": True}, False, None, 6),
    ccv("r6 CLOSED_NO_RESPONSE, wait did not time out", {"outcome": "CLOSED_NO_RESPONSE", "lastEmailWasClarification": True, "lastAwaitTimedOut": False}, False, None, 6),
    ccv("r6 CLOSED_NO_RESPONSE, facts absent", {"outcome": "CLOSED_NO_RESPONSE", "lastEmailWasClarification": None, "lastAwaitTimedOut": None}, False, None, 6),
    ccv("r7 OUT_OF_SCOPE with the decline scenario and a team decision", {"outcome": "OUT_OF_SCOPE", "latestScenario": "OUT_OF_SCOPE_ESCALATION", "teamDecision": "CLOSE_ESCALATED"}, True, "OUT_OF_SCOPE", 7),
    ccv("r8 OUT_OF_SCOPE without a team decision", {"outcome": "OUT_OF_SCOPE", "latestScenario": "OUT_OF_SCOPE_ESCALATION", "teamDecision": None}, False, None, 8),
    ccv("r8 OUT_OF_SCOPE for a CVV decline", {"outcome": "OUT_OF_SCOPE", "latestScenario": "INCORRECT_CVV", "teamDecision": "CLOSE_ESCALATED"}, False, None, 8),
    ccv("r9 ESCALATED after the team closed it", {"outcome": "ESCALATED", "teamDecision": "CLOSE_ESCALATED"}, True, "ESCALATED", 9),
    ccv("r10 ESCALATED without a team decision", {"outcome": "ESCALATED", "teamDecision": None}, False, None, 10),
    ccv("r10 ESCALATED, team resolved instead", {"outcome": "ESCALATED", "teamDecision": "RESOLVED_BY_TEAM"}, False, None, 10),
    ccv("r11 unknown outcome", {"outcome": "DONE"}, False, None, 11),
    ccv("r11 null outcome", {"outcome": None}, False, None, 11),
    ccv("r11 lower-case outcome", {"outcome": "resolved"}, False, None, 11),
]

# ------------------------------------------------------------------ TriageRoutingV2 (same table as v12, rule 6 reworded)
TRIAGE_ROUTING_V2 = list(v12.TRIAGE_ROUTING) + [
    ("r6 reworded reason (a reply introduced another card)", {**v12.TR_BASE, "requestCount": 2},
     {"triageRoute": "UNCLASSIFIED_ESCALATION", "routeReason": {"$contains": "another card or transaction"}}, 6),
]

# ------------------------------------------------------------------ CustomerResponseTypeV2
CRT_NEW = [
    ("r11 STATUS_UPDATE", {"communicationPurpose": "STATUS_UPDATE"}, {"responseType": "STATUS_UPDATE", "recipientType": "SENDER", "requiresMentorApproval": True}, 11),
    ("r12 ANSWER_QUESTION", {"communicationPurpose": "ANSWER_QUESTION"}, {"responseType": "ANSWER_QUESTION", "recipientType": "SENDER", "requiresMentorApproval": True}, 12),
    ("r13 HUMAN_ACTION_UPDATE", {"communicationPurpose": "HUMAN_ACTION_UPDATE"}, {"responseType": "HUMAN_ACTION_UPDATE", "recipientType": "SENDER", "requiresMentorApproval": True}, 13),
    ("r14 FRAUD_TEAM_CHASE", {"communicationPurpose": "FRAUD_TEAM_CHASE"}, {"responseType": "FRAUD_TEAM_CHASE", "recipientType": "FRAUD_TEAM", "requiresMentorApproval": False, "caseStatusAfterSend": "WAITING_FOR_FRAUD_TEAM"}, 14),
]
CUSTOMER_RESPONSE_TYPE_V2 = [(n, v, e, 15 if r == 11 else r) for (n, v, e, r) in v12.CUSTOMER_RESPONSE_TYPE] + CRT_NEW

# ------------------------------------------------------------------ MentorApprovalDecisionV2 (rules 2 and 3 are new; v12 rules 2-8 are now 4-10)
MENTOR_V2 = [(n, {**v, "draftSource": "MODEL"}, e, r if r == 1 else r + 2) for (n, v, e, r) in v12.MENTOR_APPROVAL_DECISION]


def ma(name, dec, rc, mx, src, action, rule):
    return (name, {"mentorDecision": dec, "reworkCount": rc, "maxRework": mx, "draftSource": src}, {"nextAction": action}, rule)


MENTOR_V2 += [
    ma("r1 APPROVE in AGENT mode", "APPROVE", 0, 3, "AGENT", "SEND", 1),
    ma("r2 REWORK in AGENT mode returns to the agent", "REWORK", 0, 3, "AGENT", "RETURN_TO_CALLER", 2),
    ma("r2 REWORK in AGENT mode ignores the counters", "REWORK", None, None, "AGENT", "RETURN_TO_CALLER", 2),
    ma("r2 REWORK in AGENT mode beyond the cap", "REWORK", 9, 3, "AGENT", "RETURN_TO_CALLER", 2),
    ma("r3 REJECT in AGENT mode returns to the agent", "REJECT", 0, 3, "AGENT", "RETURN_TO_CALLER", 3),
    ma("r9 ESCALATE in AGENT mode still escalates", "ESCALATE", 0, 3, "AGENT", "ESCALATE", 9),
    ma("r10 unknown decision in AGENT mode escalates", "MAYBE", 0, 3, "AGENT", "ESCALATE", 10),
    ma("r10 null decision in AGENT mode escalates", None, 0, 3, "AGENT", "ESCALATE", 10),
    ma("REWORK with draftSource null keeps v12 behaviour", "REWORK", 0, 3, None, "REDRAFT", 6),
    ma("REWORK with a lower-case agent is not AGENT mode", "REWORK", 0, 3, "agent", "REDRAFT", 6),
    ma("REJECT in MODEL mode still cancels", "REJECT", 0, 3, "MODEL", "CANCEL", 8),
]

ALL = {
    "IntakeRouting": INTAKE_ROUTING,
    "CustomerEmailPolicy": EMAIL_POLICY,
    "CaseCloseValidation": CASE_CLOSE,
    "TriageRoutingV2": TRIAGE_ROUTING_V2,
    "CustomerResponseTypeV2": CUSTOMER_RESPONSE_TYPE_V2,
    "MentorApprovalDecisionV2": MENTOR_V2,
}
