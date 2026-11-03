"""Case tables for the FEEL expression tests. Expressions themselves are NEVER written here:
they are read out of process/*.bpmn. This file only holds variable values and expected results."""

CONTACT = {"name": "Test Contact", "email": "contact@example.com", "role": "Programme Administrator", "isPrimary": True}

TRIAGE_FACTS = {
    "maskedCardNumber": "XXXX-XXXX-XXXX-8801", "cardLastFour": "8801", "transactionDate": "2026-06-22",
    "transactionAmount": 620.0, "transactionCurrency": "AED", "merchantName": "Example Merchant",
    "companyName": "Example Travel Ltd", "customerName": "Example Travel Ltd", "authorisedContacts": [CONTACT],
    "missingFields": [], "clientFound": True, "cardFound": True, "senderAuthorised": True, "rpaStatus": "OK",
    "agentOutputParsed": False, "agentOutputStatus": "PARSED", "recordNotFound": False, "notFoundReason": None,
    "lookupAttemptsByTool": {"dqm": 1, "mivision": 1, "echamps": 1}, "priorFollowUps": 0,
    "clarifyingQuestions": [], "searchedWith": {"cardLastFour": "8801"}, "declineReasonCode": "0076 - INV CVV",
    "cardNumberLength": 16, "detailsComplete": True,
}
EVIDENCE = {"pagesVisited": ["Home", "Card search", "Decline detail"], "capturedAt": "2026-10-29T10:00:00Z"}

BASE = {
    # start / case variables
    "caseId": "HSBC-DCL-20261029101530123", "caseStatus": "IN_TRIAGE", "caseSource": "manual",
    "senderEmail": "sender@example.com", "senderName": "Test Sender", "emailSubject": "[HSBC-CARDS] Declined transaction",
    "emailBody": "My card ending 8801 was declined on 2026-06-22 for 620 AED at Example Merchant.",
    "receivedAt": "2026-10-29T10:15:30Z", "messageId": "<test-1@example.com>",
    "fraudTeamEmail": "fraud@example.com", "demoEmailRedirect": "redirect@example.com",
    "firstResponseSla": "PT24H", "mentorSlaDuration": "PT4H", "fraudTeamSlaDuration": "PT24H", "customerReplySla": "PT15M",
    "maxFollowUps": 2, "priorFollowUps": 0, "simulatorScenario": "S6", "llmModelId": "global.anthropic.claude-sonnet-5-5",
    "auditTrail": [{"timestamp": "2026-10-29T10:15:31Z", "actor": "system", "action": "CASE_INITIALISED", "details": "x"}],
    "incomingEmail": {"caseSource": "email", "senderEmail": "sender@example.com", "senderName": "sender",
                      "emailSubject": "[HSBC-CARDS] Declined", "emailBody": "body", "messageId": "<m@example.com>",
                      "receivedAt": "2026-10-29T10:15:30Z"},
    "slaFirstResponseDue": "2026-10-30T10:15:30Z", "firstResponseAt": None,
    # triage
    "triageFacts": TRIAGE_FACTS, "triageRoute": "INCORRECT_CVV", "routeReason": "eChamps reason code 0076",
    "scenario": "INCORRECT_CVV", "scenarioLabel": "Incorrect CVV", "missingFields": [],
    "echampsResult": {"status": "FOUND", "recordFound": True, "reasonCode": "0076", "reasonCodeRaw": "0076 - INV CVV",
                      "blockCode": "NONE", "evidence": EVIDENCE},
    "mivisionResult": {"status": "FOUND", "recordFound": True, "clientFound": True, "cardFound": True,
                       "clientId": "C1", "accountNumber": "0001", "evidence": EVIDENCE},
    "dqmResult": {"status": "FOUND", "recordFound": True, "authorisedContacts": [CONTACT], "accountNumbers": ["0001"],
                  "evidence": EVIDENCE},
    "lookupAttempts": {"dqm": 1, "mivision": 1, "echamps": 1},
    "agentOutputParsed": True, "toolsCalledActual": ["LookupDqmCustomer"], "triageAgentResponseText": "{}",
    "triageAgentOutput": {"extracted": {"cardNumber": "4111111111118801", "transactionDate": "2026-06-22",
                                        "transactionAmount": "620.00", "transactionCurrency": "AED",
                                        "merchantName": "Example Merchant", "companyName": "Example Travel Ltd"},
                          "advisoryClassification": "INCORRECT_CVV", "confidence": 0.9, "clarifyingQuestions": []},
    "agent": {"context": {"conversation": {"messages": []}},
              "responseJson": {"extracted": {"cardNumber": "4111111111118801"}, "advisoryClassification": "INCORRECT_CVV"},
              "responseText": "{}"},
    "toolCall": {"_meta": {"id": "t1", "name": "Tool"}, "senderEmail": "sender@example.com", "companyName": "Example",
                 "caseNumber": "", "cardNumber": "4111 1111 1111 8801", "customerNumber": "1", "clientId": "C1",
                 "clientName": "Example", "cardFirstEight": "41111111", "cardLastFour": "8801", "accountNumber": "0001",
                 "transactionDate": "2026-06-22", "transactionAmount": "620.00"},
    "toolCallResult": {"ok": True},
    "inCardNumber": "4111 1111 1111 8801",
    "missingFieldsResult": [], "scenarioDecision": {"scenario": "INCORRECT_CVV", "scenarioLabel": "Incorrect CVV"},
    "triageRouting": {"triageRoute": "INCORRECT_CVV", "routeReason": "r"},
    "notFoundDecision": {"notFoundAction": "REQUEST_COMPLETE_DETAILS", "notFoundGuidance": "g"},
    "notFoundAction": "REQUEST_COMPLETE_DETAILS", "notFoundGuidance": "Ask for complete details.",
    "clarifyingQuestions": ["Please confirm the full card number."],
    "triageStartedAt": "2026-10-29T10:15:31Z",
    # communication
    "communicationPurpose": "MISSING_CARD_DETAILS", "recipientType": "SENDER", "requiresMentorApproval": True,
    "responseType": "REQUEST_CARD_DETAILS", "messageGuidance": "Ask for details.", "caseStatusAfterSend": "WAITING_FOR_CUSTOMER",
    "customerResponse": {"responseType": "REQUEST_CARD_DETAILS", "recipientType": "SENDER", "messageGuidance": "g",
                         "requiresMentorApproval": True, "caseStatusAfterSend": "WAITING_FOR_CUSTOMER"},
    "recipientEmail": "sender@example.com", "recipientName": "Test Sender",
    "modelDraft": {"subject": None, "body": "Dear Test Sender, ..."},
    "communicationDraft": {"subject": "RE: Declined [HSBC-DCL-20261029101530123]", "body": "Dear Test Sender, ..."},
    "mentorApproval": {"decision": "APPROVE", "comments": "ok", "approvedSubject": "RE: x [HSBC-DCL-1]",
                       "approvedBody": "Dear ...", "mentorName": "Tester", "decidedAt": "2026-10-29T10:20:00Z"},
    "approvedCommunication": {"subject": "RE: x [HSBC-DCL-1]", "body": "Dear ...", "recipientEmail": "sender@example.com",
                              "recipientName": "Test Sender"},
    "reworkCount": 0, "nextAction": "SEND", "communicationSent": True, "communicationOutcome": "SENT",
    "mentorSlaUpdate": {"slaStatus": "MENTOR_SLA_AT_RISK", "auditTrail": []},
    "decision": "APPROVE", "comments": "ok", "approvedSubject": "RE: x [HSBC-DCL-1]", "approvedBody": "Dear ...",
    "mentorName": "Tester",
    # fraud
    "fraudTeamReply": "The block has been removed; the card may be used again.",
    "fraudInterpretation": {"decision": "BLOCK_REMOVED", "confidence": 0.95, "summary": "Block removed."},
    "fraudNormalised": {"fraudTeamDecision": "BLOCK_REMOVED", "interpretationConfidence": 0.95, "fraudTeamSummary": "s"},
    "fraudTeamDecision": "BLOCK_REMOVED", "interpretationConfidence": 0.95, "aiInterpretationConfidence": 0.95,
    "aiFraudTeamDecision": "BLOCK_REMOVED", "inAiConfidence": 0.95, "fraudTeamSummary": "Fraud team confirmed removal.",
    "fraudOutcome": {"communicationPurpose": "FRAUD_OUTCOME_BLOCK_REMOVED", "needsHumanReview": False},
    "needsHumanReview": False, "fraudReviewNotes": "n/a", "chaseNotes": "Chased by phone.", "inAuditTrail": [],
    "responseJson": {"subject": "S", "body": "B", "decision": "BLOCK_REMOVED", "confidence": 0.95, "summary": "x"},
    # main-process locals / forms
    "replySenderVerified": True, "replyFrom": "sender@example.com", "locateOutcome": "LOCATED_MANUALLY",
    "locateNotes": "found", "escalationNotes": "reviewed",
    "customerReply": {"fromAddress": "sender@example.com", "subject": "RE: x [HSBC-DCL-20261029101530123]",
                      "plainTextBody": "Here are the details.\n\nOn Mon, 1 Jan 2026 Bank wrote:\n> old text",
                      "receivedAt": "2026-10-29T11:00:00Z"},
    # inbound email connector context
    "subject": "[HSBC-CARDS] Declined transaction", "fromAddress": "sender@example.com", "plainTextBody": "body text",
    "receivedDateTime": "2026-10-29T10:15:30Z",
    "headers": [{"key": "Message-ID", "value": "<m1@example.com>"}],
}

# Variables that are legitimately "no value" in production and so are not worth null-matrixing every time.
MATRIX_VALUES = [None, False, True, "null"]  # plus ABSENT (variable not defined)

# ----------------------------------------------------------------------------------------------
# Routing: (gateway id) -> list of (case name, variable overrides, expected flow id[, soft note])
# The chosen flow is computed the way the engine does: first outgoing flow, in document order, whose
# condition is true; otherwise the default flow. Conditions are the ones extracted from the BPMN.
# `soft` marks a fail-closed hardening expectation (reported as WARN, not FAIL).
# ----------------------------------------------------------------------------------------------
CLARIF = ["MISSING_CARD_DETAILS", "INVALID_CARD_NUMBER", "MISSING_REQUIRED_DATA", "CARD_COMPANY_MISMATCH",
          "UNAUTHORISED_SENDER", "REQUEST_COMPLETE_DETAILS"]

ROUTING = {
    "Gateway_PurposeSupported": (
        [("SENDER", {"recipientType": "SENDER"}, "Flow_Purpose_Ok"),
         ("AUTHORISED_CONTACT", {"recipientType": "AUTHORISED_CONTACT"}, "Flow_Purpose_Ok"),
         ("FRAUD_TEAM", {"recipientType": "FRAUD_TEAM"}, "Flow_Purpose_Ok"),
         ("NONE", {"recipientType": "NONE"}, "Flow_Purpose_None"),
         ("null", {"recipientType": None}, "Flow_Purpose_None")]),
    "Gateway_NeedsMentor": (
        [("flag true, body present", {"requiresMentorApproval": True}, "Flow_NeedsMentor_Yes"),
         ("flag false, body present", {"requiresMentorApproval": False}, "Flow_NeedsMentor_No"),
         ("flag false, empty body forces mentor", {"requiresMentorApproval": False, "communicationDraft": {"subject": "s", "body": ""}}, "Flow_NeedsMentor_Yes"),
         ("flag false, null body forces mentor", {"requiresMentorApproval": False, "communicationDraft": {"subject": "s", "body": None}}, "Flow_NeedsMentor_Yes"),
         ("flag false, null draft forces mentor", {"requiresMentorApproval": False, "communicationDraft": None}, "Flow_NeedsMentor_Yes"),
         ("flag null is fail-closed (hardening)", {"requiresMentorApproval": None}, "Flow_NeedsMentor_Yes", "null requiresMentorApproval skips the Mentor; the DMN always returns true/false so this cannot occur today"),
         ]),
    "Gateway_NextAction": (
        [("SEND", {"nextAction": "SEND"}, "Flow_Next_Send"),
         ("REDRAFT", {"nextAction": "REDRAFT"}, "Flow_Next_Redraft"),
         ("CANCEL", {"nextAction": "CANCEL"}, "Flow_Next_Cancel"),
         ("ESCALATE", {"nextAction": "ESCALATE"}, "Flow_Next_Escalate"),
         ("null", {"nextAction": None}, "Flow_Next_Escalate"),
         ("unknown", {"nextAction": "BOGUS"}, "Flow_Next_Escalate")]),
    "Gateway_NeedsHumanReview": (
        [("true", {"needsHumanReview": True}, "Flow_Review_Yes"),
         ("false", {"needsHumanReview": False}, "Flow_Review_No"),
         ("null is fail-closed (hardening)", {"needsHumanReview": None}, "Flow_Review_Yes", "null needsHumanReview skips the human review; the DMN catch-all returns true so this cannot occur today")]),
    "Gateway_TriageRoute": (
        [("clarif " + r, {"triageRoute": r}, "Flow_RouteClarification") for r in CLARIF]
        + [("INCORRECT_CVV", {"triageRoute": "INCORRECT_CVV"}, "Flow_RouteIncorrectCvv"),
           ("FRAUD_ALERT", {"triageRoute": "FRAUD_ALERT"}, "Flow_RouteFraudAlert"),
           ("RECORD_NOT_FOUND_ESCALATION", {"triageRoute": "RECORD_NOT_FOUND_ESCALATION"}, "Flow_RouteLocateRecord")]
        + [("escalation " + str(r), {"triageRoute": r}, "Flow_RouteEscalation")
           for r in ["UNCLASSIFIED_ESCALATION", "OUT_OF_SCOPE_ESCALATION", "RPA_FAILURE_ESCALATION", None, "BOGUS"]]),
    "Gateway_EndState": (
        [("RESOLVED", {"caseStatus": "RESOLVED"}, "Flow_EndResolved"),
         ("WAITING_FOR_CUSTOMER", {"caseStatus": "WAITING_FOR_CUSTOMER"}, "Flow_EndWaitingCustomer"),
         ("WAITING_FOR_FRAUD_TEAM", {"caseStatus": "WAITING_FOR_FRAUD_TEAM"}, "Flow_EndWaitingFraud"),
         ("OUT_OF_SCOPE", {"caseStatus": "OUT_OF_SCOPE"}, "Flow_EndOutOfScope"),
         ("CLOSED_NO_RESPONSE", {"caseStatus": "CLOSED_NO_RESPONSE"}, "Flow_EndNoResponse"),
         ("ESCALATED -> default", {"caseStatus": "ESCALATED"}, "Flow_EndEscalated"),
         ("null -> default", {"caseStatus": None}, "Flow_EndEscalated"),
         ("unknown -> default", {"caseStatus": "BOGUS"}, "Flow_EndEscalated")]),
    "Gateway_FollowUpCap": (
        [("clarif, prior 2 max 2 -> cap", {"triageRoute": "MISSING_CARD_DETAILS", "priorFollowUps": 2, "maxFollowUps": 2}, "Flow_CapReached"),
         ("clarif, prior 3 max 2 -> cap", {"triageRoute": "REQUEST_COMPLETE_DETAILS", "priorFollowUps": 3, "maxFollowUps": 2}, "Flow_CapReached"),
         ("unauthorised sender at cap", {"triageRoute": "UNAUTHORISED_SENDER", "priorFollowUps": 2, "maxFollowUps": 2}, "Flow_CapReached"),
         ("clarif, prior 1 max 2 -> continue", {"triageRoute": "MISSING_CARD_DETAILS", "priorFollowUps": 1, "maxFollowUps": 2}, "Flow_CapToRoute"),
         ("prior null counts as 0", {"triageRoute": "MISSING_CARD_DETAILS", "priorFollowUps": None, "maxFollowUps": 2}, "Flow_CapToRoute"),
         ("max null defaults to 2", {"triageRoute": "MISSING_CARD_DETAILS", "priorFollowUps": 2, "maxFollowUps": None}, "Flow_CapReached"),
         ("both null -> continue", {"triageRoute": "MISSING_CARD_DETAILS", "priorFollowUps": None, "maxFollowUps": None}, "Flow_CapToRoute"),
         ("non-clarification route never capped", {"triageRoute": "INCORRECT_CVV", "priorFollowUps": 9, "maxFollowUps": 2}, "Flow_CapToRoute"),
         ("fraud route never capped", {"triageRoute": "FRAUD_ALERT", "priorFollowUps": 9, "maxFollowUps": 2}, "Flow_CapToRoute"),
         ("route null -> continue", {"triageRoute": None, "priorFollowUps": 9, "maxFollowUps": 2}, "Flow_CapToRoute")]),
    "Gateway_ClarificationSent": (
        [("sent and waiting", {"communicationSent": True, "caseStatus": "WAITING_FOR_CUSTOMER"}, "Flow_ClarificationSentToWait"),
         ("sent but resolved", {"communicationSent": True, "caseStatus": "RESOLVED"}, "Flow_ClarificationNotSent"),
         ("not sent", {"communicationSent": False, "caseStatus": "WAITING_FOR_CUSTOMER"}, "Flow_ClarificationNotSent"),
         ("null sent", {"communicationSent": None, "caseStatus": "WAITING_FOR_CUSTOMER"}, "Flow_ClarificationNotSent"),
         ("null status", {"communicationSent": True, "caseStatus": None}, "Flow_ClarificationNotSent")]),
    "Gateway_ReplySenderVerified": (
        [("verified", {"replySenderVerified": True}, "Flow_ReplyVerified"),
         ("unverified", {"replySenderVerified": False}, "Flow_ReplyUnverified"),
         ("null -> unverified (fail closed)", {"replySenderVerified": None}, "Flow_ReplyUnverified")]),
    "Gateway_RecordNotFound": (
        [("RECORD_NOT_FOUND", {"triageRoute": "RECORD_NOT_FOUND"}, "Flow_NotFoundYes"),
         ("INCORRECT_CVV", {"triageRoute": "INCORRECT_CVV"}, "Flow_NotFoundNo"),
         ("null", {"triageRoute": None}, "Flow_NotFoundNo")]),
}

# ----------------------------------------------------------------------------------------------
# Value tests for non-gateway expressions: (process id, element id, kind, target) -> [(name, vars, expected)]
# `vars` override BASE. `expected` uses lib.common.match (subset for dicts, {"$re": ..} for patterns).
# ----------------------------------------------------------------------------------------------
MAIN = "HSBC_Commercial_Cards_Declined_Transaction_Triage"
COMM = "HSBC_Customer_Communication"
FRAUD = "HSBC_Decline_Fraud_Alert"
TRIAGE = "HSBC_Transaction_Triage_Agent"
RE_TAG_CASE = "HSBC-DCL-20261029101530123"

VALUES = {
    (MAIN, "StartEvent_EmailReceived", "property", "activationCondition"): [
        ("new case mail", {"subject": "[HSBC-CARDS] decline", "headers": []}, True),
        ("tag lower case", {"subject": "[hsbc-cards] decline", "headers": []}, True),
        ("headers null", {"subject": "[HSBC-CARDS] decline", "headers": None}, True),
        ("reply (In-Reply-To) is not new", {"subject": "[HSBC-CARDS] decline", "headers": [{"key": "In-Reply-To", "value": "<x>"}]}, False),
        ("customer reply tag excluded", {"subject": "RE: [HSBC-CARDS] x [HSBC-DCL-1]", "headers": []}, False),
        ("fraud tag excluded", {"subject": "RE: [HSBC-CARDS] x [HSBC-FRD-1]", "headers": []}, False),
        ("no tag", {"subject": "hello", "headers": []}, False),
        ("null subject", {"subject": None, "headers": []}, False)],
    (MAIN, "Catch_CustomerReply", "property", "activationCondition"): [
        ("reply", {"subject": "RE: x [HSBC-DCL-123]"}, True),
        ("reply lower case", {"subject": "re: x [hsbc-dcl-123]"}, True),
        ("fraud mail is not a customer reply", {"subject": "RE: x [HSBC-FRD-123]"}, False),
        ("both tags -> fraud wins", {"subject": "RE: [HSBC-DCL-1] [HSBC-FRD-1]"}, False),
        ("no tag", {"subject": "hello"}, False), ("null subject", {"subject": None}, False)],
    (MAIN, "Catch_CustomerReply", "property", "correlationKeyExpression"): [
        ("plain", {"subject": "RE: x [HSBC-DCL-20261029101530123]"}, "HSBC-DCL-20261029101530123"),
        ("lower case tag", {"subject": "re: x [hsbc-dcl-20261029101530123]"}, "HSBC-DCL-20261029101530123")],
    (FRAUD, "Catch_FraudTeamResponse", "property", "activationCondition"): [
        ("fraud reply", {"subject": "RE: x [HSBC-FRD-123]"}, True),
        ("lower case", {"subject": "re: x [hsbc-frd-123]"}, True),
        ("customer tag", {"subject": "RE: x [HSBC-DCL-123]"}, False), ("null subject", {"subject": None}, False)],
    (FRAUD, "Catch_FraudTeamResponse", "property", "correlationKeyExpression"): [
        ("maps FRD digits to the caseId", {"subject": "RE: x [HSBC-FRD-20261029101530123]"}, RE_TAG_CASE),
        ("lower case", {"subject": "re: x [hsbc-frd-20261029101530123]"}, RE_TAG_CASE)],
    (MAIN, "StartEvent_EmailReceived", "property", "messageIdExpression"): [
        ("header present", {"headers": [{"key": "Message-ID", "value": "<abc>"}]}, "<abc>"),
        ("header absent falls back", {"headers": [], "subject": "S", "fromAddress": "a@example.com"}, "S|a@example.com")],
    (TRIAGE, "ValidateCardNumber", "script", "toolCallResult"): [
        ("16 digits with spaces", {"inCardNumber": "4111 1111 1111 8801"}, {"digits": "4111111111118801", "length": 16, "isComplete": True, "firstEight": "41111111", "lastFour": "8801"}),
        ("15 digits", {"inCardNumber": "411111111111880"}, {"length": 15, "isComplete": False}),
        ("17 digits", {"inCardNumber": "41111111111188011"}, {"length": 17, "isComplete": False}),
        ("masked", {"inCardNumber": "XXXX-XXXX-XXXX-8801"}, {"digits": "8801", "length": 4, "isComplete": False, "firstEight": None, "lastFour": "8801"}),
        ("null", {"inCardNumber": None}, {"digits": "", "length": 0, "isComplete": False}),
        ("empty", {"inCardNumber": ""}, {"length": 0, "isComplete": False})],
    (MAIN, "Task_RecordOutcome", "script", "caseOutcome"): [
        ("met", {"slaFirstResponseDue": "2026-10-30T10:00:00Z", "firstResponseAt": "2026-10-29T10:00:00Z"}, {"slaStatus": "MET"}),
        ("breached", {"slaFirstResponseDue": "2026-10-29T09:00:00Z", "firstResponseAt": "2026-10-29T10:00:00Z"}, {"slaStatus": "BREACHED"}),
        ("no due date", {"slaFirstResponseDue": None}, {"slaStatus": "UNKNOWN"})],
    (MAIN, "Task_MarkEscalated", "script", "caseStatus"): [
        ("out of scope route", {"caseStatus": "IN_TRIAGE", "triageRoute": "OUT_OF_SCOPE_ESCALATION"}, "OUT_OF_SCOPE"),
        ("other route", {"caseStatus": "IN_TRIAGE", "triageRoute": "UNCLASSIFIED_ESCALATION"}, "ESCALATED"),
        ("keeps OUT_OF_SCOPE", {"caseStatus": "OUT_OF_SCOPE", "triageRoute": "UNCLASSIFIED_ESCALATION"}, "OUT_OF_SCOPE")],
    (MAIN, "Task_MergeCustomerReply", "script", "replyMerge"): [
        ("quoted history stripped", {}, {"replyFrom": "sender@example.com", "caseStatus": "IN_TRIAGE"}),
        ("from as list with display name", {"customerReply": {"fromAddress": ["Test <Sender@Example.com>"], "plainTextBody": "hi", "receivedAt": "2026-10-29T11:00:00Z"}}, {"replyFrom": "sender@example.com", "caseStatus": "IN_TRIAGE"}),
        ("null reply tolerated", {"customerReply": None}, {"caseStatus": "IN_TRIAGE"})],
    (COMM, "Task_ResolveRecipient", "script", "recipient"): [
        ("sender", {"recipientType": "SENDER"}, {"recipientEmail": "sender@example.com", "recipientName": "Test Sender"}),
        ("authorised contact", {"recipientType": "AUTHORISED_CONTACT"}, {"recipientEmail": "contact@example.com"}),
        ("fraud team", {"recipientType": "FRAUD_TEAM"}, {"recipientEmail": "fraud@example.com", "recipientName": "Fraud Prevention Team"})],
    (COMM, "Task_BuildDraftSubject", "script", "communicationDraft"): [
        ("customer tag is the caseId", {"recipientType": "SENDER", "emailSubject": "Declined", "modelDraft": {"body": "B"}}, {"subject": "RE: Declined [HSBC-DCL-20261029101530123]", "body": "B"}),
        ("fraud team gets the FRD tag", {"recipientType": "FRAUD_TEAM", "emailSubject": "Declined", "modelDraft": {"body": "B"}}, {"subject": "RE: Declined [HSBC-FRD-20261029101530123]"}),
        ("no model draft -> null body", {"modelDraft": None}, {"body": None})],
    (COMM, "Task_FlagMentorSlaBreach", "script", "mentorSlaUpdate"): [
        ("flags", {}, {"slaStatus": "MENTOR_SLA_AT_RISK"})],
    (COMM, "Task_IncrementRework", "script", "reworkUpdate"): [
        ("0 -> 1", {"reworkCount": 0}, {"reworkCount": 1}), ("2 -> 3", {"reworkCount": 2}, {"reworkCount": 3})],
    (COMM, "Task_RecordCommunication", "script", "communicationResult"): [
        ("sent", {"caseStatusAfterSend": "RESOLVED"}, {"communicationSent": True, "caseStatus": "RESOLVED", "communicationOutcome": "SENT"})],
    (COMM, "Task_RecordCancellation", "script", "cancellationResult"): [
        ("cancelled", {}, {"communicationSent": False, "communicationOutcome": "CANCELLED", "caseStatus": "ESCALATED"})],
    (COMM, "Task_RecordEscalation", "script", "escalationResult"): [
        ("escalated", {}, {"communicationSent": False, "communicationOutcome": "ESCALATED", "caseStatus": "ESCALATED"})],
    (FRAUD, "Task_NormaliseFraudInterpretation", "script", "fraudNormalised"): [
        ("clean", {"fraudInterpretation": {"decision": "KEEP_BLOCK_REISSUE", "confidence": 0.9, "summary": "s"}}, {"fraudTeamDecision": "KEEP_BLOCK_REISSUE", "interpretationConfidence": 0.9, "fraudTeamSummary": "s"}),
        ("confidence as string", {"fraudInterpretation": {"decision": "BLOCK_REMOVED", "confidence": "0.85", "summary": "s"}}, {"interpretationConfidence": 0.85}),
        ("null interpretation -> UNCLEAR/0", {"fraudInterpretation": None}, {"fraudTeamDecision": "UNCLEAR", "interpretationConfidence": 0}),
        ("null decision -> UNCLEAR", {"fraudInterpretation": {"decision": None, "confidence": 0.9, "summary": None}}, {"fraudTeamDecision": "UNCLEAR"})],
}
