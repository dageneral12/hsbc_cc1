"""DMN case tables. Input names are the ones in process/dmn/*.dmn (read by run_dmn.py, which also checks
that every rule index has at least one case).

Each case: (name, variables, expected output subset, expected rule index or None)
For COLLECT tables the expected value is a list and the rule index is a list of indexes.
"""

TR_BASE = {"rpaStatus": "OK", "clientFound": True, "senderAuthorised": True, "cardNumberLength": 16,
           "missingFieldCount": 0, "cardFound": True, "scenario": "INCORRECT_CVV",
           "declineReasonCode": "0076 - INV CVV", "notFoundReason": None, "recordNotFound": False,
           "requestCount": 1}


def tr(name, over, route, rule):
    return (name, {**TR_BASE, **over}, {"triageRoute": route}, rule)


TRIAGE_ROUTING = [
    # rule 1
    tr("r1 rpaStatus ERROR", {"rpaStatus": "ERROR"}, "RPA_FAILURE_ESCALATION", 1),
    tr("r1 rpaStatus null", {"rpaStatus": None}, "RPA_FAILURE_ESCALATION", 1),
    # rule 2
    tr("r2 CLIENT_NOT_FOUND", {"notFoundReason": "CLIENT_NOT_FOUND", "recordNotFound": True, "cardFound": None}, "RECORD_NOT_FOUND", 2),
    tr("r2 CUSTOMER_NOT_FOUND", {"notFoundReason": "CUSTOMER_NOT_FOUND", "recordNotFound": True, "clientFound": None, "senderAuthorised": None}, "RECORD_NOT_FOUND", 2),
    # rule 3
    tr("r3 clientFound false", {"clientFound": False}, "UNCLASSIFIED_ESCALATION", 3),
    tr("r3 clientFound null", {"clientFound": None}, "UNCLASSIFIED_ESCALATION", 3),
    # rule 4 / 5
    tr("r4 senderAuthorised null", {"senderAuthorised": None}, "UNCLASSIFIED_ESCALATION", 4),
    tr("r5 senderAuthorised false", {"senderAuthorised": False}, "UNAUTHORISED_SENDER", 5),
    # rule 6 / 7 / 8
    tr("r6 cardNumberLength null", {"cardNumberLength": None}, "UNCLASSIFIED_ESCALATION", 7),
    tr("r7 no card number", {"cardNumberLength": 0}, "MISSING_CARD_DETAILS", 8),
    tr("r8 15 digits", {"cardNumberLength": 15}, "INVALID_CARD_NUMBER", 9),
    tr("r8 17 digits", {"cardNumberLength": 17}, "INVALID_CARD_NUMBER", 9),
    # rule 9 / 10
    tr("r9 missingFieldCount null", {"missingFieldCount": None}, "UNCLASSIFIED_ESCALATION", 10),
    tr("r10 missing fields", {"missingFieldCount": 2}, "MISSING_REQUIRED_DATA", 11),
    # rule 11 (S3) / 12 / 13
    tr("r11 S3 card not under client", {"cardFound": False}, "CARD_COMPANY_MISMATCH", 12),
    tr("r12 record not found (eChamps)", {"recordNotFound": True, "notFoundReason": "NO_MATCHING_AUTH"}, "RECORD_NOT_FOUND", 13),
    tr("r12 record not found, card not found", {"recordNotFound": True, "notFoundReason": "CARD_NOT_FOUND"}, "RECORD_NOT_FOUND", 13),
    tr("r13 cardFound null", {"cardFound": None}, "UNCLASSIFIED_ESCALATION", 14),
    # rule 14-17
    tr("r14 INCORRECT_CVV", {"scenario": "INCORRECT_CVV"}, "INCORRECT_CVV", 15),
    tr("r15 FRAUD_ALERT", {"scenario": "FRAUD_ALERT", "declineReasonCode": "0713 - FALC DECL"}, "FRAUD_ALERT", 16),
    tr("r16 OUT_OF_SCOPE", {"scenario": "OUT_OF_SCOPE_ESCALATION", "declineReasonCode": "0005"}, "OUT_OF_SCOPE_ESCALATION", 17),
    tr("r17 UNKNOWN scenario", {"scenario": "UNKNOWN", "declineReasonCode": None}, "UNCLASSIFIED_ESCALATION", 18),
    tr("r17 null scenario", {"scenario": None}, "UNCLASSIFIED_ESCALATION", 18),
    tr("r17 unrecognised scenario", {"scenario": "BOGUS"}, "UNCLASSIFIED_ESCALATION", 18),
    # rule-17 regression: recordNotFound false/null must never yield RECORD_NOT_FOUND with CVV / fraud facts
    tr("regression CVV recordNotFound=false", {"scenario": "INCORRECT_CVV", "recordNotFound": False}, "INCORRECT_CVV", 15),
    tr("regression CVV recordNotFound=null", {"scenario": "INCORRECT_CVV", "recordNotFound": None}, "INCORRECT_CVV", 15),
    tr("regression FRAUD recordNotFound=false", {"scenario": "FRAUD_ALERT", "recordNotFound": False}, "FRAUD_ALERT", 16),
    tr("regression FRAUD recordNotFound=null", {"scenario": "FRAUD_ALERT", "recordNotFound": None}, "FRAUD_ALERT", 16),
    # S3 beats the not-found rule
    tr("S3 beats not-found (cardFound=false + recordNotFound)", {"cardFound": False, "recordNotFound": True, "notFoundReason": "CARD_NOT_UNDER_CLIENT"}, "CARD_COMPANY_MISMATCH", 12),
    tr("S3 beats not-found (eChamps reason)", {"cardFound": False, "recordNotFound": True, "notFoundReason": "CARD_NOT_FOUND"}, "CARD_COMPANY_MISMATCH", 12),
    # ordering: sender checks come before card checks
    tr("unauthorised beats missing card number", {"senderAuthorised": False, "cardNumberLength": 0}, "UNAUTHORISED_SENDER", 5),
    tr("RPA error beats everything", {"rpaStatus": "ERROR", "senderAuthorised": False, "cardNumberLength": 0}, "RPA_FAILURE_ESCALATION", 1),
    # rule 6: interim multi-request guardrail (more than one declined transaction in one email)
    tr("r6 two requests", {"requestCount": 2}, "UNCLASSIFIED_ESCALATION", 6),
    tr("r6 three requests, missing card", {"requestCount": 3, "cardNumberLength": 0}, "UNCLASSIFIED_ESCALATION", 6),
    tr("single request unchanged", {"requestCount": 1}, "INCORRECT_CVV", 15),
    tr("requestCount null unchanged", {"requestCount": None}, "INCORRECT_CVV", 15),
    tr("unauthorised beats multi-request", {"requestCount": 2, "senderAuthorised": False}, "UNAUTHORISED_SENDER", 5),
]
# null inputs must escalate (never a customer-facing or decline-scenario route): input -> expected route
TR_NULL_INPUTS = {
    "rpaStatus": "RPA_FAILURE_ESCALATION", "clientFound": "UNCLASSIFIED_ESCALATION",
    "senderAuthorised": "UNCLASSIFIED_ESCALATION", "cardNumberLength": "UNCLASSIFIED_ESCALATION",
    "missingFieldCount": "UNCLASSIFIED_ESCALATION", "cardFound": "UNCLASSIFIED_ESCALATION",
    "scenario": "UNCLASSIFIED_ESCALATION",
}
TR_ESCALATIONS = {"RPA_FAILURE_ESCALATION", "UNCLASSIFIED_ESCALATION", "OUT_OF_SCOPE_ESCALATION", "RECORD_NOT_FOUND"}
# routes that act on the card / customer: only reachable when RPA OK, client found, sender authorised, card found
TR_ACTING = {"INCORRECT_CVV", "FRAUD_ALERT"}

DEFAULT_REASON = {"scenario": None}

REASON_TO_SCENARIO = [
    ("r1 0076 raw", {"declineReasonCode": "0076 - INV CVV"}, {"scenario": "INCORRECT_CVV"}, 1),
    ("r1 0076 plain", {"declineReasonCode": "0076"}, {"scenario": "INCORRECT_CVV"}, 1),
    ("r1 0076 with spaces", {"declineReasonCode": "  0076  "}, {"scenario": "INCORRECT_CVV"}, 1),
    ("r2 0713 raw", {"declineReasonCode": "0713 / FALC DECL"}, {"scenario": "FRAUD_ALERT"}, 2),
    ("r2 0713 plain", {"declineReasonCode": "0713"}, {"scenario": "FRAUD_ALERT"}, 2),
    ("r3 null", {"declineReasonCode": None}, {"scenario": "UNKNOWN"}, 3),
    ("r3 empty", {"declineReasonCode": ""}, {"scenario": "UNKNOWN"}, 3),
    ("r3 blank", {"declineReasonCode": "   "}, {"scenario": "UNKNOWN"}, 3),
    ("r4 other code", {"declineReasonCode": "0005 - DO NOT HONOUR"}, {"scenario": "OUT_OF_SCOPE_ESCALATION"}, 4),
    ("r4 short code", {"declineReasonCode": "76"}, {"scenario": "OUT_OF_SCOPE_ESCALATION"}, 4),
    ("r4 no digits", {"declineReasonCode": "INV CVV"}, {"scenario": "OUT_OF_SCOPE_ESCALATION"}, 4),
    ("r4 look-alike 0760", {"declineReasonCode": "0760"}, {"scenario": "OUT_OF_SCOPE_ESCALATION"}, 4),
]

REQ_FIELDS_OK = {"transactionDate": "2026-06-22", "transactionAmount": 620, "merchantName": "Example Merchant"}
REQUIRED_FIELDS = [  # COLLECT: expected list of missingField values, rule indexes
    ("none missing", {**REQ_FIELDS_OK}, [], []),
    ("date null", {**REQ_FIELDS_OK, "transactionDate": None}, ["transactionDate"], [1]),
    ("date empty", {**REQ_FIELDS_OK, "transactionDate": ""}, ["transactionDate"], [1]),
    ("date blank (trimmed)", {**REQ_FIELDS_OK, "transactionDate": "   "}, ["transactionDate"], [1]),
    ("amount null", {**REQ_FIELDS_OK, "transactionAmount": None}, ["transactionAmount"], [2]),
    ("amount zero", {**REQ_FIELDS_OK, "transactionAmount": 0}, ["transactionAmount"], [2]),
    ("amount negative", {**REQ_FIELDS_OK, "transactionAmount": -5}, ["transactionAmount"], [2]),
    ("merchant null", {**REQ_FIELDS_OK, "merchantName": None}, ["merchantName"], [3]),
    ("merchant blank (trimmed)", {**REQ_FIELDS_OK, "merchantName": "  "}, ["merchantName"], [3]),
    ("all missing, rule order", {"transactionDate": None, "transactionAmount": None, "merchantName": None},
     ["transactionDate", "transactionAmount", "merchantName"], [1, 2, 3]),
    ("date + merchant missing", {**REQ_FIELDS_OK, "transactionDate": None, "merchantName": ""}, ["transactionDate", "merchantName"], [1, 3]),
]

NF_BASE = {"notFoundReason": "NO_MATCHING_AUTH", "detailsComplete": True, "lookupAttempts": 1, "priorFollowUps": 0}


def nf(name, over, action, rule):
    return (name, {**NF_BASE, **over}, {"notFoundAction": action}, rule)


RECORD_NOT_FOUND_ACTION = [
    nf("r1 already asked once", {"priorFollowUps": 1}, "ESCALATE_RECORD_NOT_FOUND", 1),
    nf("r1 asked twice", {"priorFollowUps": 2, "notFoundReason": "CUSTOMER_NOT_FOUND"}, "ESCALATE_RECORD_NOT_FOUND", 1),
    nf("r1 priorFollowUps null", {"priorFollowUps": None}, "ESCALATE_RECORD_NOT_FOUND", 1),
    nf("r2 customer not found, first attempt", {"notFoundReason": "CUSTOMER_NOT_FOUND"}, "REQUEST_COMPLETE_DETAILS", 2),
    nf("r2 customer not found, details incomplete", {"notFoundReason": "CUSTOMER_NOT_FOUND", "detailsComplete": False}, "REQUEST_COMPLETE_DETAILS", 2),
    nf("r3 client not found (system mismatch)", {"notFoundReason": "CLIENT_NOT_FOUND"}, "ESCALATE_RECORD_NOT_FOUND", 3),
    nf("r3 client not found, details incomplete", {"notFoundReason": "CLIENT_NOT_FOUND", "detailsComplete": False}, "ESCALATE_RECORD_NOT_FOUND", 3),
    nf("r4 detailsComplete null", {"detailsComplete": None}, "ESCALATE_RECORD_NOT_FOUND", 4),
    nf("r5 details incomplete", {"notFoundReason": "CARD_NOT_FOUND", "detailsComplete": False}, "REQUEST_COMPLETE_DETAILS", 5),
    nf("r6 no matching authorisation", {"notFoundReason": "NO_MATCHING_AUTH"}, "REQUEST_COMPLETE_DETAILS", 6),
    nf("r7 card not found", {"notFoundReason": "CARD_NOT_FOUND"}, "ESCALATE_RECORD_NOT_FOUND", 7),
    nf("r8 reason null", {"notFoundReason": None}, "ESCALATE_RECORD_NOT_FOUND", 8),
    nf("r8 reason unrecognised", {"notFoundReason": "BOGUS"}, "ESCALATE_RECORD_NOT_FOUND", 8),
    nf("r8 CARD_NOT_UNDER_CLIENT (S3 reason)", {"notFoundReason": "CARD_NOT_UNDER_CLIENT"}, "ESCALATE_RECORD_NOT_FOUND", 8),
]

CRT_FRAUD = "FRAUD_TEAM_REVIEW_REQUEST"
CUSTOMER_RESPONSE_TYPE = [
    ("r1 MISSING_CARD_DETAILS", {"communicationPurpose": "MISSING_CARD_DETAILS"}, {"responseType": "REQUEST_CARD_DETAILS", "recipientType": "SENDER", "requiresMentorApproval": True, "caseStatusAfterSend": "WAITING_FOR_CUSTOMER"}, 1),
    ("r2 INVALID_CARD_NUMBER", {"communicationPurpose": "INVALID_CARD_NUMBER"}, {"responseType": "REQUEST_FULL_CARD_NUMBER", "recipientType": "SENDER", "requiresMentorApproval": True, "caseStatusAfterSend": "WAITING_FOR_CUSTOMER"}, 2),
    ("r3 MISSING_REQUIRED_DATA", {"communicationPurpose": "MISSING_REQUIRED_DATA"}, {"responseType": "REQUEST_MISSING_DATA", "recipientType": "SENDER", "requiresMentorApproval": True, "caseStatusAfterSend": "WAITING_FOR_CUSTOMER"}, 3),
    ("r4 CARD_COMPANY_MISMATCH", {"communicationPurpose": "CARD_COMPANY_MISMATCH"}, {"responseType": "CARD_NOT_FOUND_NOTICE", "recipientType": "SENDER", "requiresMentorApproval": True, "caseStatusAfterSend": "WAITING_FOR_CUSTOMER"}, 4),
    ("r5 UNAUTHORISED_SENDER", {"communicationPurpose": "UNAUTHORISED_SENDER"}, {"responseType": "UNAUTHORISED_SENDER_NOTICE", "recipientType": "AUTHORISED_CONTACT", "requiresMentorApproval": True, "caseStatusAfterSend": "WAITING_FOR_CUSTOMER"}, 5),
    ("r6 CVV_RETRY_ADVICE", {"communicationPurpose": "CVV_RETRY_ADVICE"}, {"responseType": "CVV_RETRY_ADVICE", "recipientType": "SENDER", "requiresMentorApproval": True, "caseStatusAfterSend": "RESOLVED"}, 6),
    ("r7 FRAUD_TEAM_REVIEW_REQUEST", {"communicationPurpose": CRT_FRAUD}, {"responseType": CRT_FRAUD, "recipientType": "FRAUD_TEAM", "requiresMentorApproval": False, "caseStatusAfterSend": "WAITING_FOR_FRAUD_TEAM"}, 7),
    ("r8 FRAUD_OUTCOME_BLOCK_REMOVED", {"communicationPurpose": "FRAUD_OUTCOME_BLOCK_REMOVED"}, {"responseType": "FRAUD_BLOCK_REMOVED_NOTICE", "recipientType": "SENDER", "requiresMentorApproval": True, "caseStatusAfterSend": "RESOLVED"}, 8),
    ("r9 FRAUD_OUTCOME_KEEP_BLOCK", {"communicationPurpose": "FRAUD_OUTCOME_KEEP_BLOCK"}, {"responseType": "FRAUD_BLOCK_REMAINS_NOTICE", "recipientType": "SENDER", "requiresMentorApproval": True, "caseStatusAfterSend": "RESOLVED"}, 9),
    ("r10 REQUEST_COMPLETE_DETAILS", {"communicationPurpose": "REQUEST_COMPLETE_DETAILS"}, {"responseType": "REQUEST_COMPLETE_DETAILS", "recipientType": "SENDER", "requiresMentorApproval": True, "caseStatusAfterSend": "WAITING_FOR_CUSTOMER"}, 10),
    ("r11 unknown purpose", {"communicationPurpose": "SOMETHING_ELSE"}, {"responseType": "UNSUPPORTED_PURPOSE", "recipientType": "NONE", "caseStatusAfterSend": "ESCALATED"}, 11),
    ("r11 null purpose", {"communicationPurpose": None}, {"recipientType": "NONE", "caseStatusAfterSend": "ESCALATED"}, 11),
    ("r11 lower-case purpose is not matched", {"communicationPurpose": "missing_card_details"}, {"recipientType": "NONE"}, 11),
]

FO = lambda name, dec, conf, purpose, review, rule: (name, {"fraudTeamDecision": dec, "interpretationConfidence": conf}, {"communicationPurpose": purpose, "needsHumanReview": review}, rule)  # noqa: E731
FRAUD_MANAGEMENT_OUTCOME = [
    FO("r1 UNCLEAR", "UNCLEAR", 0.95, None, True, 1),
    FO("r1 MORE_INFO_REQUIRED", "MORE_INFO_REQUIRED", 0.99, None, True, 1),
    FO("r2 low confidence 0.79", "BLOCK_REMOVED", 0.79, None, True, 2),
    FO("r2 confidence null", "KEEP_BLOCK_REISSUE", None, None, True, 2),
    FO("r2 confidence 0", "BLOCK_REMOVED", 0, None, True, 2),
    FO("r3 BLOCK_REMOVED 0.8 boundary", "BLOCK_REMOVED", 0.8, "FRAUD_OUTCOME_BLOCK_REMOVED", False, 3),
    FO("r3 BLOCK_REMOVED 1.0", "BLOCK_REMOVED", 1.0, "FRAUD_OUTCOME_BLOCK_REMOVED", False, 3),
    FO("r4 KEEP_BLOCK_REISSUE 0.9", "KEEP_BLOCK_REISSUE", 0.9, "FRAUD_OUTCOME_KEEP_BLOCK", False, 4),
    FO("r5 decision null", None, 0.95, None, True, 5),
    FO("r5 decision unrecognised", "MAYBE", 0.95, None, True, 5),
    FO("r5 decision lower case", "block_removed", 0.95, None, True, 5),
    FO("r5 both null", None, None, None, True, 2),  # r2 (null confidence) fires first; still human review
]

MA = lambda name, dec, rc, mx, action, rule: (name, {"mentorDecision": dec, "reworkCount": rc, "maxRework": mx}, {"nextAction": action}, rule)  # noqa: E731
MENTOR_APPROVAL_DECISION = [
    MA("r1 APPROVE", "APPROVE", 0, 3, "SEND", 1),
    MA("r1 APPROVE ignores rework counters", "APPROVE", None, None, "SEND", 1),
    MA("r2 REWORK, reworkCount null", "REWORK", None, 3, "ESCALATE", 2),
    MA("r3 REWORK, maxRework null", "REWORK", 0, None, "ESCALATE", 3),
    MA("r4 REWORK 0 of 3", "REWORK", 0, 3, "REDRAFT", 4),
    MA("r4 REWORK 2 of 3", "REWORK", 2, 3, "REDRAFT", 4),
    MA("r5 REWORK at limit", "REWORK", 3, 3, "ESCALATE", 5),
    MA("r5 REWORK over limit", "REWORK", 4, 3, "ESCALATE", 5),
    MA("r6 REJECT", "REJECT", 0, 3, "CANCEL", 6),
    MA("r7 ESCALATE", "ESCALATE", 0, 3, "ESCALATE", 7),
    MA("r8 null decision", None, 0, 3, "ESCALATE", 8),
    MA("r8 unknown decision", "MAYBE", 0, 3, "ESCALATE", 8),
    MA("r8 lower-case approve is not APPROVE", "approve", 0, 3, "ESCALATE", 8),
    MA("r8 empty decision", "", 0, 3, "ESCALATE", 8),
]

# Invariant grids (run by run_dmn.py)
MENTOR_DECISIONS = ["APPROVE", "REWORK", "REJECT", "ESCALATE", None, "null", "approve", "", "APPROVED", True]
MENTOR_REWORK = [None, 0, 2, 3, 4]
MENTOR_MAX = [None, 3]

TRIAGE_GRID = {
    "rpaStatus": ["OK", "ERROR", None],
    "clientFound": [True, False, None],
    "senderAuthorised": [True, False, None],
    "cardFound": [True, False, None],
    "scenario": ["INCORRECT_CVV", "FRAUD_ALERT", "OUT_OF_SCOPE_ESCALATION", "UNKNOWN", None],
}

ALL = {
    "TriageRouting": TRIAGE_ROUTING,
    "DeclineReasonToScenario": REASON_TO_SCENARIO,
    "RequiredTriageFields": REQUIRED_FIELDS,
    "RecordNotFoundAction": RECORD_NOT_FOUND_ACTION,
    "CustomerResponseType": CUSTOMER_RESPONSE_TYPE,
    "FraudManagementOutcome": FRAUD_MANAGEMENT_OUTCOME,
    "MentorApprovalDecision": MENTOR_APPROVAL_DECISION,
}
