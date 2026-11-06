# process-v2 → process-v3: full model diff

Semantic diff of every BPMN, DMN and form. Diagram geometry, documentation prose and
element ordering are excluded; everything else that is configurable is compared.
Files with no differences are listed at the end.

## File-level changes

| Change | v2 | v3 |
|---|---|---|
| retired | `hsbc-scenario-triage.bpmn` | `retired/hsbc-scenario-triage.bpmn` (kept, not deployed) |
| retired | `dmn/simulator-scenario-from-card.dmn` | `retired/simulator-scenario-from-card.dmn` (kept, not deployed) |
| added | — | `hsbc-messageid-correlation-test.bpmn` — test harness built 2026-11-06, **not part of the demo** |
| renamed | `dmn/customer-response-type-v2.dmn` | `dmn/customer-response-type-v3.dmn` |
| renamed | `dmn/mentor-approval-decision-v2.dmn` | `dmn/mentor-approval-decision-v3.dmn` |
| renamed | `dmn/triage-routing-v2.dmn` | `dmn/triage-routing-v3.dmn` |
| renamed | `forms/mentor-approval-v2.form` | `forms/mentor-approval-v3.form` |

## Summary of changes per file

`id only` means the resource id gained a `_V3` / `-v3` suffix and nothing else changed.

| File | elements/fields added | removed | params changed | rule tables changed |
|---|---|---|---|---|
| `hsbc-agentic-triage.bpmn` |  | 1 | 11 |  |
| `hsbc-email-intake.bpmn` |  |  | 4 |  |
| `hsbc-decline-request-agent.bpmn` |  |  | 18 |  |
| `hsbc-customer-communication-agentic.bpmn` |  |  | 5 |  |
| `hsbc-tool-investigate-card-decline.bpmn` |  | 1 | 6 |  |
| `hsbc-tool-interpret-fraud-reply.bpmn` |  |  | 1 |  |
| `hsbc-request-late-reply-wait.bpmn` |  |  | 2 |  |
| `case-close-validation.dmn` | _id only_ | | | |
| `customer-email-policy.dmn` | _id only_ | | | |
| `customer-response-type-v2.dmn` → `customer-response-type-v3.dmn` | _id only_ | | | |
| `decline-reason-to-scenario.dmn` | _id only_ | | | |
| `fraud-management-outcome.dmn` | _id only_ | | | |
| `intake-routing.dmn` | _id only_ | | | |
| `mentor-approval-decision-v2.dmn` → `mentor-approval-decision-v3.dmn` | _id only_ | | | |
| `record-not-found-action.dmn` |  |  |  | 1 |
| `required-triage-fields.dmn` | _id only_ | | | |
| `triage-routing-v2.dmn` → `triage-routing-v3.dmn` | _id only_ | | | |
| `escalation-review.form` | _id only_ | | | |
| `fraud-response-review.form` | _id only_ | | | |
| `locate-record.form` | _id only_ | | | |
| `mentor-approval-v2.form` → `mentor-approval-v3.form` | 1 |  |  |  |
| `request-handover.form` | _id only_ | | | |


---

## `hsbc-agentic-triage.bpmn`

**Process definition**

- v2 id: `HSBC_Commercial_Cards_Agentic_Triage` — name `HSBC Commercial Cards Agentic Triage`
- v3 id: `HSBC_Commercial_Cards_Agentic_Triage_V3` — name `HSBC Commercial Cards Agentic Triage`

**Elements removed in v3**

- `CallActivity_ScenarioTriage` (callActivity) — "Scenario triage (demo plumbing)"

**`CallActivity_Clarification`** (callActivity) — "Email-level notice to the customer (unauthorised sender, details missing)"

**parameters**

- `calledElement.processId`
    - v2: `HSBC_Customer_Communication_Agentic`
    - v3: `HSBC_Customer_Communication_Agentic_V3`
- `input::simulatorBaseUrl`
    - v2: _(absent)_
    - v3: `=if is defined(simulatorBaseUrl) then simulatorBaseUrl else null`

**`CallActivity_Intake`** (callActivity) — "Intake (extraction, DQM, sender check, routing)"

**parameters**

- `calledElement.processId`
    - v2: `HSBC_Email_Intake`
    - v3: `HSBC_Email_Intake_V3`
- `input::simulatorBaseUrl`
    - v2: _(absent)_
    - v3: `=if is defined(simulatorBaseUrl) then simulatorBaseUrl else null`
- `input::simulatorScenario`
    - v2: `=simulatorScenario`
    - v3: _(absent)_

**`CallActivity_RequestJourney`** (callActivity) — "Request journey (agent)"

**parameters**

- `calledElement.processId`
    - v2: `HSBC_Decline_Request_Agent`
    - v3: `HSBC_Decline_Request_Agent_V3`
- `input::simulatorBaseUrl`
    - v2: _(absent)_
    - v3: `=if is defined(simulatorBaseUrl) then simulatorBaseUrl else null`
- `input::simulatorScenario`
    - v2: `=simulatorScenario`
    - v3: _(absent)_

**`Catch_CustomerReply`** (intermediateCatchEvent) — "Customer replied"

**parameters**

- `prop::activationCondition`
    - v2: `=subject != null and matches(upper case(subject), ".*\[HSBC-AGT-[0-9]+\].*") and not(contains(upper case(subject), "[HSBC-AFR-")) and receivedDateTime != null and date and time(string(receivedDateTime)) > now() - duration("PT24H")`
    - v3: `=subject != null and matches(upper case(subject), ".*\[HSBC-V3-[0-9]+\].*") and not(contains(upper case(subject), "[HSBC-AFV3-")) and receivedDateTime != null and date and time(string(receivedDateTime)) > now() - duration("PT24H")`
- `prop::correlationKeyExpression`
    - v2: `=replace(upper case(subject), ".*\[(HSBC-AGT-[0-9]+)\].*", "$1")`
    - v3: `=replace(upper case(subject), ".*\[(HSBC-V3-[0-9]+)\].*", "$1")`
- `prop::data.folderToListen`
    - v2: `INBOX`
    - v3: `INBOX.2026-11-03-nikita-nt-dec-06`
- `prop::deduplicationId`
    - v2: `hsbc-agt-main-reply`
    - v3: `hsbc-v3-main-reply`

**`StartEvent_EmailReceived`** (startEvent) — "Customer email received"

**parameters**

- `prop::activationCondition`
    - v2: `=subject != null and contains(upper case(subject), "[HSBC-CARDS-AI]") and (headers = null or is empty(headers[key = "In-Reply-To"])) and not(contains(upper case(subject), "[HSBC-AGT-")) and not(contains(upper case(subject), "[HSBC-AFR-")) and receivedDateTime != null and date and time(string(receive …`
    - v3: `=subject != null and contains(upper case(subject), "[HSBC-CARDS-V3]") and (headers = null or is empty(headers[key = "In-Reply-To"])) and not(contains(upper case(subject), "[HSBC-V3-")) and not(contains(upper case(subject), "[HSBC-AFV3-")) and receivedDateTime != null and date and time(string(receive …`
- `prop::data.folderToListen`
    - v2: `INBOX`
    - v3: `INBOX.2026-11-03-nikita-nt-dec-06`
- `prop::deduplicationId`
    - v2: `hsbc-agt-main-start`
    - v3: `hsbc-v3-main-start`

**`Task_ExtractInlineImages`** (serviceTask) — "Extract inline images (RPA)"

**parameters**

- `input::SIMULATOR_BASE_URL`
    - v2: _(absent)_
    - v3: `=if is defined(simulatorBaseUrl) and simulatorBaseUrl != null then simulatorBaseUrl else ""`
- `input::mailFolder`
    - v2: `INBOX`
    - v3: `INBOX.2026-11-03-nikita-nt-dec-06`
- `linkedResource.RPAScript`
    - v2: `RPA_hsbcInlineImages`
    - v3: `RPA_hsbcInlineImages_V3`

**`Task_InitialiseCase`** (scriptTask) — "Initialise case"

**parameters**

- `output::simulatorScenario`
    - v2: `=caseInit.simulatorScenario`
    - v3: _(absent)_
- `script.expression` — changed (3803 → 3715 chars)
  ```diff
  @@ -7 +7 @@
  -  inCaseId: "HSBC-AGT-" + substring(replace(string(now()), "[^0-9]", ""), 1, 17),
  +  inCaseId: "HSBC-V3-" + substring(replace(string(now()), "[^0-9]", ""), 1, 17),
  @@ -25 +25 @@
  -    conversationWindow: if conversationWindow != null then conversationWindow else "PT20M",
  +    conversationWindow: if conversationWindow != null then conversationWindow else "PT5M",
  @@ -27 +27 @@
  -    lateReplyWindow: if lateReplyWindow != null then lateReplyWindow else "PT1H",
  +    lateReplyWindow: if lateReplyWindow != null then lateReplyWindow else "PT5M",
  @@ -42 +41,0 @@
  -    simulatorScenario: if simulatorScenario != null then simulatorScenario else null,
  ```

**`UserTask_HandleEscalation`** (userTask) — "Handle escalated case"

**parameters**

- `formDefinition.formId`
    - v2: `hsbc-escalation-review`
    - v3: `hsbc-escalation-review-v3`

**`UserTask_LocateRecord`** (userTask) — "Locate record manually"

**parameters**

- `formDefinition.formId`
    - v2: `hsbc-locate-record`
    - v3: `hsbc-locate-record-v3`

**messages `Message_1idpu2v`**

**changed**

- `name`
    - v2: `hsbc-agt-triage-email`
    - v3: `hsbc-v3-triage-email`

**messages `Message_CustomerReply`**

**changed**

- `name`
    - v2: `hsbc-agt-customer-reply`
    - v3: `hsbc-v3-customer-reply`

---

## `hsbc-email-intake.bpmn`

**Process definition**

- v2 id: `HSBC_Email_Intake` — name `HSBC Email Intake`
- v3 id: `HSBC_Email_Intake_V3` — name `HSBC Email Intake`

**`BRT_IntakeRouting`** (businessRuleTask) — "Decide intake route"

**parameters**

- `calledDecision.decisionId`
    - v2: `IntakeRouting`
    - v3: `IntakeRouting_V3`

**`BRT_RecordNotFoundAction`** (businessRuleTask) — "Decide record-not-found action"

**parameters**

- `calledDecision.decisionId`
    - v2: `RecordNotFoundAction`
    - v3: `RecordNotFoundAction_V3`

**`Task_LookupDqm`** (serviceTask) — "DQM customer lookup (RPA)"

**parameters**

- `input::SIMULATOR_BASE_URL`
    - v2: _(absent)_
    - v3: `=if is defined(simulatorBaseUrl) and simulatorBaseUrl != null then simulatorBaseUrl else ""`
- `input::simulatorScenario`
    - v2: `=if is defined(simulatorScenario) then simulatorScenario else null`
    - v3: _(absent)_
- `linkedResource.RPAScript`
    - v2: `RPA_1sctslp`
    - v3: `RPA_1sctslp_V3`

**`Task_LookupDqmBySender`** (serviceTask) — "DQM lookup by sender only (RPA)"

**parameters**

- `input::SIMULATOR_BASE_URL`
    - v2: _(absent)_
    - v3: `=if is defined(simulatorBaseUrl) and simulatorBaseUrl != null then simulatorBaseUrl else ""`
- `input::simulatorScenario`
    - v2: `=if is defined(simulatorScenario) then simulatorScenario else null`
    - v3: _(absent)_
- `linkedResource.RPAScript`
    - v2: `RPA_1sctslp`
    - v3: `RPA_1sctslp_V3`

---

## `hsbc-decline-request-agent.bpmn`

**Process definition**

- v2 id: `HSBC_Decline_Request_Agent` — name `HSBC Decline Request Agent`
- v3 id: `HSBC_Decline_Request_Agent_V3` — name `HSBC Decline Request Agent`

**`BRT_CaseCloseValidation`** (businessRuleTask) — "Validate the close"

**parameters**

- `calledDecision.decisionId`
    - v2: `CaseCloseValidation`
    - v3: `CaseCloseValidation_V3`

**`BRT_CaseCloseValidation_Post`** (businessRuleTask) — "Validate the close (post-agent)"

**parameters**

- `calledDecision.decisionId`
    - v2: `CaseCloseValidation`
    - v3: `CaseCloseValidation_V3`

**`BRT_CustomerEmailPolicy`** (businessRuleTask) — "Check customer email policy"

**parameters**

- `calledDecision.decisionId`
    - v2: `CustomerEmailPolicy`
    - v3: `CustomerEmailPolicy_V3`

**`CallActivity_AwaitLateReply`** (callActivity) — "Wait for a late reply"

**parameters**

- `calledElement.processId`
    - v2: `HSBC_Request_LateReplyWait`
    - v3: `HSBC_Request_LateReplyWait_V3`
- `input::simulatorBaseUrl`
    - v2: _(absent)_
    - v3: `=if is defined(simulatorBaseUrl) then simulatorBaseUrl else null`

**`CallActivity_InterpretFraud`** (callActivity) — "Interpret fraud reply (AI)"

**parameters**

- `calledElement.processId`
    - v2: `HSBC_Tool_InterpretFraudReply`
    - v3: `HSBC_Tool_InterpretFraudReply_V3`
- `input::simulatorBaseUrl`
    - v2: _(absent)_
    - v3: `=if is defined(simulatorBaseUrl) then simulatorBaseUrl else null`

**`CallActivity_Investigate`** (callActivity) — "Investigate (MiVision, eChamps, DMNs)"

**parameters**

- `calledElement.processId`
    - v2: `HSBC_Tool_InvestigateCardDecline`
    - v3: `HSBC_Tool_InvestigateCardDecline_V3`
- `input::simulatorBaseUrl`
    - v2: _(absent)_
    - v3: `=if is defined(simulatorBaseUrl) then simulatorBaseUrl else null`
- `input::simulatorScenario`
    - v2: `=if is defined(simulatorScenario) then simulatorScenario else null`
    - v3: _(absent)_

**`CallActivity_SendCustomerEmail`** (callActivity) — "Send customer email (Mentor-approved)"

**parameters**

- `calledElement.processId`
    - v2: `HSBC_Customer_Communication_Agentic`
    - v3: `HSBC_Customer_Communication_Agentic_V3`
- `input::fraudTeamSummary`
    - v2: _(absent)_
    - v3: `=if get value(ledger, "latestFraudInterp") = null then null else ledger.latestFraudInterp.fraudTeamSummary`
- `input::simulatorBaseUrl`
    - v2: _(absent)_
    - v3: `=if is defined(simulatorBaseUrl) then simulatorBaseUrl else null`

**`CallActivity_SendFraudEmail`** (callActivity) — "Email the fraud team"

**parameters**

- `calledElement.processId`
    - v2: `HSBC_Customer_Communication_Agentic`
    - v3: `HSBC_Customer_Communication_Agentic_V3`
- `input::simulatorBaseUrl`
    - v2: _(absent)_
    - v3: `=if is defined(simulatorBaseUrl) then simulatorBaseUrl else null`

**`Catch_FraudTeamResponse`** (intermediateCatchEvent) — "Fraud team replied"

**parameters**

- `prop::activationCondition`
    - v2: `=subject != null and contains(upper case(subject), "[HSBC-AFR-") and receivedDateTime != null and date and time(string(receivedDateTime)) > now() - duration("P7D")`
    - v3: `=subject != null and contains(upper case(subject), "[HSBC-AFV3-") and receivedDateTime != null and date and time(string(receivedDateTime)) > now() - duration("P7D")`
- `prop::correlationKeyExpression`
    - v2: `=replace(upper case(subject), ".*\[HSBC-AFR-([0-9]+-[0-9]+)\].*", "HSBC-AGT-$1")`
    - v3: `=replace(upper case(subject), ".*\[HSBC-AFV3-([0-9]+-[0-9]+)\].*", "HSBC-V3-$1")`
- `prop::data.folderToListen`
    - v2: `INBOX`
    - v3: `INBOX.2026-11-03-nikita-nt-dec-06`
- `prop::deduplicationId`
    - v2: `hsbc-agt-req-fraud-reply`
    - v3: `hsbc-v3-req-fraud-reply`

**`Start_CustomerReply`** (startEvent) — "Customer replied"

**parameters**

- `prop::activationCondition`
    - v2: `=subject != null and matches(upper case(subject), ".*\[HSBC-AGT-[0-9]+-[0-9]+\].*") and not(contains(upper case(subject), "[HSBC-AFR-")) and receivedDateTime != null and date and time(string(receivedDateTime)) > now() - duration("PT10M")`
    - v3: `=subject != null and matches(upper case(subject), ".*\[HSBC-V3-[0-9]+-[0-9]+\].*") and not(contains(upper case(subject), "[HSBC-AFV3-")) and receivedDateTime != null and date and time(string(receivedDateTime)) > now() - duration("PT10M")`
- `prop::correlationKeyExpression`
    - v2: `=replace(upper case(subject), ".*\[(HSBC-AGT-[0-9]+-[0-9]+)\].*", "$1")`
    - v3: `=replace(upper case(subject), ".*\[(HSBC-V3-[0-9]+-[0-9]+)\].*", "$1")`
- `prop::data.folderToListen`
    - v2: `INBOX`
    - v3: `INBOX.2026-11-03-nikita-nt-dec-06`
- `prop::deduplicationId`
    - v2: `hsbc-agt-req-reply-start`
    - v3: `hsbc-v3-req-reply-start`

**`Task_ExtractReplyImages`** (serviceTask) — "Extract inline images from the reply (RPA)"

**parameters**

- `input::SIMULATOR_BASE_URL`
    - v2: _(absent)_
    - v3: `=if is defined(simulatorBaseUrl) and simulatorBaseUrl != null then simulatorBaseUrl else ""`
- `input::mailFolder`
    - v2: `INBOX`
    - v3: `INBOX.2026-11-03-nikita-nt-dec-06`
- `linkedResource.RPAScript`
    - v2: `RPA_hsbcInlineImages`
    - v3: `RPA_hsbcInlineImages_V3`

**`Task_GuardEmail`** (scriptTask) — "Guard: body, duplicates, step"

**parameters**

- `script.expression` — changed (1646 → 1654 chars)
  ```diff
  @@ -3 +3 @@
  -  stripped: replace(replace(b, "HSBC-(AGT|AFR)-[0-9]+(-[0-9]+)?", ""), "(?<=[0-9])[ \\-](?=[0-9])", ""),
  +  stripped: replace(replace(b, "HSBC-(AGT|AFR|AFV3|V3)-[0-9]+(-[0-9]+)?", ""), "(?<=[0-9])[ \\-](?=[0-9])", ""),
  ```

**`Task_InitRequest`** (scriptTask) — "Initialise request journey"

**parameters**

- `output::simulatorScenario`
    - v2: `=requestInit.simulatorScenario`
    - v3: _(absent)_
- `script.expression` — changed (7237 → 7145 chars)
  ```diff
  @@ -19 +19 @@
  -    conversationWindow: d(if is defined(conversationWindow) then conversationWindow else null, "PT20M"),
  +    conversationWindow: d(if is defined(conversationWindow) then conversationWindow else null, "PT5M"),
  @@ -22 +22 @@
  -    lateReplyWindow: d(if is defined(lateReplyWindow) then lateReplyWindow else null, "PT1H"),
  +    lateReplyWindow: d(if is defined(lateReplyWindow) then lateReplyWindow else null, "PT5M"),
  @@ -32 +31,0 @@
  -    simulatorScenario: if is defined(simulatorScenario) then simulatorScenario else null,
  @@ -59 +58 @@
  -      + "; conversation window after your last email: " + d(if is defined(conversationWindow) then conversationWindow else null, "PT20M")
  +      + "; conversation window after your last email: " + d(if is defined(conversationWindow) then conversationWindow else null, "PT5M")
  ```

**`UserTask_HandToTeam`** (userTask) — "Hand request to the team"

**parameters**

- `formDefinition.formId`
    - v2: `hsbc-request-handover`
    - v3: `hsbc-request-handover-v3`

**`UserTask_ReviewFraudResponse`** (userTask) — "Review fraud response"

**parameters**

- `formDefinition.formId`
    - v2: `hsbc-fraud-response-review`
    - v3: `hsbc-fraud-response-review-v3`

**`UserTask_TakeOverRequest`** (userTask) — "Take over the request"

**parameters**

- `formDefinition.formId`
    - v2: `hsbc-request-handover`
    - v3: `hsbc-request-handover-v3`

**messages `Message_FraudTeamReply`**

**changed**

- `name`
    - v2: `hsbc-agt-fraud-team-response`
    - v3: `hsbc-v3-fraud-team-response`

**messages `Message_RequestReply`**

**changed**

- `name`
    - v2: `hsbc-agt-request-reply`
    - v3: `hsbc-v3-request-reply`

---

## `hsbc-customer-communication-agentic.bpmn`

**Process definition**

- v2 id: `HSBC_Customer_Communication_Agentic` — name `HSBC Customer Communication (agentic)`
- v3 id: `HSBC_Customer_Communication_Agentic_V3` — name `HSBC Customer Communication (agentic)`

**`BRT_CustomerResponseType`** (businessRuleTask) — "Determine response type"

**parameters**

- `calledDecision.decisionId`
    - v2: `CustomerResponseTypeV2`
    - v3: `CustomerResponseType_V3`

**`BRT_MentorApprovalDecision`** (businessRuleTask) — "Decide next action"

**parameters**

- `calledDecision.decisionId`
    - v2: `MentorApprovalDecisionV2`
    - v3: `MentorApprovalDecision_V3`

**`Task_BuildDraftSubject`** (scriptTask) — "Build reply subject"

**parameters**

- `script.expression`
    - v2: `={subject: "RE: " + get or else(string(emailSubject), "(no subject)") + " [" + (if recipientType = "FRAUD_TEAM" then "HSBC-AFR-" + substring after(caseId, "HSBC-AGT-") else caseId) + "]", body: if modelDraft != null then modelDraft.body else null}`
    - v3: `={subject: "RE: " + get or else(string(emailSubject), "(no subject)") + " [" + (if recipientType = "FRAUD_TEAM" then "HSBC-AFV3-" + substring after(caseId, "HSBC-V3-") else caseId) + "]", body: if modelDraft != null then modelDraft.body else null}`

**`Task_PciScan`** (scriptTask) — "PCI scan of the body"

**parameters**

- `script.expression` — changed (414 → 422 chars)
  ```diff
  @@ -3 +3 @@
  -  stripped: if inBody = null then "" else replace(replace(inBody, "HSBC-(AGT|AFR)-[0-9]+(-[0-9]+)?", ""), "(?<=[0-9])[ \\-](?=[0-9])", ""),
  +  stripped: if inBody = null then "" else replace(replace(inBody, "HSBC-(AGT|AFR|AFV3|V3)-[0-9]+(-[0-9]+)?", ""), "(?<=[0-9])[ \\-](?=[0-9])", ""),
  ```

**`UserTask_MentorApproval`** (userTask) — "Approve customer email"

**parameters**

- `formDefinition.formId`
    - v2: `hsbc-mentor-approval-v2`
    - v3: `hsbc-mentor-approval-v3`

---

## `hsbc-tool-investigate-card-decline.bpmn`

**Process definition**

- v2 id: `HSBC_Tool_InvestigateCardDecline` — name `HSBC Tool - Investigate Card Decline`
- v3 id: `HSBC_Tool_InvestigateCardDecline_V3` — name `HSBC Tool - Investigate Card Decline`

**Elements removed in v3**

- `BRT_ScenarioRefresh` (businessRuleTask) — "Refresh simulator scenario (demo plumbing)"

**`BRT_DeclineReasonToScenario`** (businessRuleTask) — "Map decline reason to scenario"

**parameters**

- `calledDecision.decisionId`
    - v2: `DeclineReasonToScenario`
    - v3: `DeclineReasonToScenario_V3`

**`BRT_RecordNotFoundAction`** (businessRuleTask) — "Decide record-not-found action"

**parameters**

- `calledDecision.decisionId`
    - v2: `RecordNotFoundAction`
    - v3: `RecordNotFoundAction_V3`
- `input::cardForm`
    - v2: _(absent)_
    - v3: `=if mivisionResult = null then null else get value(mivisionResult, "cardForm")`

**`BRT_RequiredTriageFields`** (businessRuleTask) — "Check required fields"

**parameters**

- `calledDecision.decisionId`
    - v2: `RequiredTriageFields`
    - v3: `RequiredTriageFields_V3`

**`BRT_TriageRouting`** (businessRuleTask) — "Decide recommended route"

**parameters**

- `calledDecision.decisionId`
    - v2: `TriageRoutingV2`
    - v3: `TriageRouting_V3`

**`Task_LookupEChamps`** (serviceTask) — "eChamps decline investigation (RPA)"

**parameters**

- `input::SIMULATOR_BASE_URL`
    - v2: _(absent)_
    - v3: `=if is defined(simulatorBaseUrl) and simulatorBaseUrl != null then simulatorBaseUrl else ""`
- `input::simulatorScenario`
    - v2: `=if is defined(simulatorScenario) then simulatorScenario else null`
    - v3: _(absent)_
- `linkedResource.RPAScript`
    - v2: `RPA_0daw5hw`
    - v3: `RPA_0daw5hw_V3`

**`Task_LookupMiVision`** (serviceTask) — "MiVision client and card lookup (RPA)"

**parameters**

- `input::SIMULATOR_BASE_URL`
    - v2: _(absent)_
    - v3: `=if is defined(simulatorBaseUrl) and simulatorBaseUrl != null then simulatorBaseUrl else ""`
- `input::simulatorScenario`
    - v2: `=if is defined(simulatorScenario) then simulatorScenario else null`
    - v3: _(absent)_
- `linkedResource.RPAScript`
    - v2: `RPA_09aoltb`
    - v3: `RPA_09aoltb_V3`

---

## `hsbc-tool-interpret-fraud-reply.bpmn`

**Process definition**

- v2 id: `HSBC_Tool_InterpretFraudReply` — name `HSBC Tool - Interpret Fraud Reply`
- v3 id: `HSBC_Tool_InterpretFraudReply_V3` — name `HSBC Tool - Interpret Fraud Reply`

**`BRT_FraudManagementOutcome`** (businessRuleTask) — "Decide fraud outcome"

**parameters**

- `calledDecision.decisionId`
    - v2: `FraudManagementOutcome`
    - v3: `FraudManagementOutcome_V3`

---

## `hsbc-request-late-reply-wait.bpmn`

**Process definition**

- v2 id: `HSBC_Request_LateReplyWait` — name `HSBC Request Late Reply Wait`
- v3 id: `HSBC_Request_LateReplyWait_V3` — name `HSBC Request Late Reply Wait`

**`Catch_LateReply`** (intermediateCatchEvent) — "Late reply"

**parameters**

- `prop::activationCondition`
    - v2: `=subject != null and matches(upper case(subject), ".*\[HSBC-AGT-[0-9]+-[0-9]+\].*") and not(contains(upper case(subject), "[HSBC-AFR-")) and receivedDateTime != null and date and time(string(receivedDateTime)) > now() - duration("PT45S")`
    - v3: `=subject != null and matches(upper case(subject), ".*\[HSBC-V3-[0-9]+-[0-9]+\].*") and not(contains(upper case(subject), "[HSBC-AFV3-")) and receivedDateTime != null and date and time(string(receivedDateTime)) > now() - duration("PT45S")`
- `prop::correlationKeyExpression`
    - v2: `=replace(upper case(subject), ".*\[(HSBC-AGT-[0-9]+-[0-9]+)\].*", "$1")`
    - v3: `=replace(upper case(subject), ".*\[(HSBC-V3-[0-9]+-[0-9]+)\].*", "$1")`
- `prop::data.folderToListen`
    - v2: `INBOX`
    - v3: `INBOX.2026-11-03-nikita-nt-dec-06`
- `prop::deduplicationId`
    - v2: `hsbc-agt-late-reply`
    - v3: `hsbc-v3-late-reply`

**messages `Message_LateReply`**

**changed**

- `name`
    - v2: `hsbc-agt-request-late-reply`
    - v3: `hsbc-v3-request-late-reply`

---

## `dmn/case-close-validation.dmn`

**Decision ids**

- v2 only: `CaseCloseValidation` — "Case Close Validation"
- v3 only: `CaseCloseValidation_V3` — "Case Close Validation"

---

## `dmn/customer-email-policy.dmn`

**Decision ids**

- v2 only: `CustomerEmailPolicy` — "Customer Email Policy"
- v3 only: `CustomerEmailPolicy_V3` — "Customer Email Policy"

---

## `dmn/customer-response-type-v2.dmn` → `dmn/customer-response-type-v3.dmn`

**Decision ids**

- v2 only: `CustomerResponseTypeV2` — "Customer Response Type V2"
- v3 only: `CustomerResponseType_V3` — "Customer Response Type V2"

---

## `dmn/decline-reason-to-scenario.dmn`

**Decision ids**

- v2 only: `DeclineReasonToScenario` — "Decline Reason To Scenario"
- v3 only: `DeclineReasonToScenario_V3` — "Decline Reason To Scenario"

---

## `dmn/fraud-management-outcome.dmn`

**Decision ids**

- v2 only: `FraudManagementOutcome` — "Fraud Management Outcome"
- v3 only: `FraudManagementOutcome_V3` — "Fraud Management Outcome"

---

## `dmn/intake-routing.dmn`

**Decision ids**

- v2 only: `IntakeRouting` — "Intake Routing"
- v3 only: `IntakeRouting_V3` — "Intake Routing"

---

## `dmn/mentor-approval-decision-v2.dmn` → `dmn/mentor-approval-decision-v3.dmn`

**Decision ids**

- v2 only: `MentorApprovalDecisionV2` — "Mentor Approval Decision V2"
- v3 only: `MentorApprovalDecision_V3` — "Mentor Approval Decision V2"

---

## `dmn/record-not-found-action.dmn`

**Decision ids**

- v2 only: `RecordNotFoundAction` — "Record Not Found Action"
- v3 only: `RecordNotFoundAction_V3` — "Record Not Found Action"

**Decision `RecordNotFoundAction` → `RecordNotFoundAction_V3`** — "Record Not Found Action"
- inputs: 4 → 5
    - col 5 v2: _(absent)_
    - col 5 v3: `cardForm = cardForm`
- rules: **8 → 11**
  ```diff
  @@ -1,8 +1,11 @@
  --  |  -  |  -  |  >= 1, null  |  =>  |  "ESCALATE_RECORD_NOT_FOUND"  |  "Internal note for the case handler (never sent to the customer). The customer was already asked for details once, or the number of earlier follow-ups is unknown. Do not email again; locate the record manually using the searched values and RPA evidence."
  -"CUSTOMER_NOT_FOUND"  |  -  |  -  |  -  |  =>  |  "REQUEST_COMPLETE_DETAILS"  |  "Ask the sender only for identifying details so we can find their customer record: the company legal name and the customer number or programme number. Say only that the request cannot be progressed with the details provided. Never say whether a customer, client, card or transaction exists, and do not say what was searched or what failed
  -"CLIENT_NOT_FOUND"  |  -  |  -  |  -  |  =>  |  "ESCALATE_RECORD_NOT_FOUND"  |  "Internal note for the case handler (never sent to the customer). DQM found the customer but MiVision could not find the client: a system mismatch. Check the MiVision client / customer number manually and decide how to respond. No email is sent."
  --  |  null  |  -  |  -  |  =>  |  "ESCALATE_RECORD_NOT_FOUND"  |  "Internal note for the case handler (never sent to the customer). It could not be determined whether the customer details are complete. Review the case manually."
  --  |  false  |  -  |  -  |  =>  |  "REQUEST_COMPLETE_DETAILS"  |  "Ask the sender for the complete set of details: the last four digits of the card, the company name, the transaction date, the amount and currency, and the merchant name. Say only that the request cannot be progressed with the details provided; never say whether a client, card or transaction exists."
  -"NO_MATCHING_AUTH"  |  -  |  -  |  -  |  =>  |  "REQUEST_COMPLETE_DETAILS"  |  "The card was found but no declined authorisation matched the transaction. Ask the sender to confirm the transaction date, amount, currency and merchant name exactly as shown on the statement or card app. Do not say that no matching transaction exists; say only that the request cannot be progressed with the details provided."
  -"CARD_NOT_FOUND"  |  -  |  -  |  -  |  =>  |  "ESCALATE_RECORD_NOT_FOUND"  |  "Internal note for the case handler (never sent to the customer). MiVision found the card but eChamps did not; the two systems disagree. Check the account number and the card manually."
  --  |  -  |  -  |  -  |  =>  |  "ESCALATE_RECORD_NOT_FOUND"  |  "Internal note for the case handler (never sent to the customer). The not-found reason is null or not recognised. Review manually."
  +-  |  -  |  -  |  >= 1, null  |  -  |  =>  |  "ESCALATE_RECORD_NOT_FOUND"  |  "Internal note for the case handler (never sent to the customer). The customer was already asked for details once, or the number of earlier follow-ups is unknown. Do not email again; locate the record manually using the searched values and RPA evidence."
  +"CUSTOMER_NOT_FOUND"  |  -  |  -  |  -  |  -  |  =>  |  "REQUEST_COMPLETE_DETAILS"  |  "Ask the sender only for identifying details so we can find their customer record: the company legal name and the customer number or programme number. Say only that the request cannot be progressed with the details provided. Never say whether a customer, client, card or transaction exists, and do not say what was searched or what 
  +"CLIENT_NOT_FOUND"  |  -  |  -  |  -  |  -  |  =>  |  "ESCALATE_RECORD_NOT_FOUND"  |  "Internal note for the case handler (never sent to the customer). DQM found the customer but MiVision could not find the client: a system mismatch. Check the MiVision client / customer number manually and decide how to respond. No email is sent."
  +-  |  null  |  -  |  -  |  -  |  =>  |  "ESCALATE_RECORD_NOT_FOUND"  |  "Internal note for the case handler (never sent to the customer). It could not be determined whether the customer details are complete. Review the case manually."
  +-  |  false  |  -  |  -  |  -  |  =>  |  "REQUEST_COMPLETE_DETAILS"  |  "Ask the sender for the complete set of details: the last four digits of the card, the company name, the transaction date, the amount and currency, and the merchant name. Say only that the request cannot be progressed with the details provided; never say whether a client, card or transaction exists."
  +"NO_AUTH_RECORDS"  |  -  |  -  |  -  |  "VIRTUAL"  |  =>  |  "ESCALATE_RECORD_NOT_FOUND"  |  "Internal note for the case handler (never sent to the customer). This is a virtual card. Virtual-card declines are raised by InControl, not by the authorisation host, so eChamps will never hold a row for them and re-confirming the transaction cannot help. Open the purchase request for this card in SDG2 and read the InContro
  +"NO_AUTH_RECORDS"  |  -  |  -  |  -  |  -  |  =>  |  "ESCALATE_RECORD_NOT_FOUND"  |  "Internal note for the case handler (never sent to the customer). eChamps holds no authorisation records at all for this card, so there is nothing for the customer's date and amount to be matched against and asking again cannot help. Check the card and the account manually in MiVision and eChamps."
  +"NO_DECLINE_ON_CARD"  |  -  |  -  |  -  |  -  |  =>  |  "ESCALATE_RECORD_NOT_FOUND"  |  "Internal note for the case handler (never sent to the customer). The card has authorisation activity but no decline of any kind, so the decline never reached the authorisation host. Follow the network path: check GHCS for a ticket raised on this card, then Mastercard Connect for the network decline. Do not ask the customer to re
  +"NO_MATCHING_AUTH"  |  -  |  -  |  -  |  -  |  =>  |  "REQUEST_COMPLETE_DETAILS"  |  "The card was found but no declined authorisation matched the transaction. Ask the sender to confirm the transaction date, amount, currency and merchant name exactly as shown on the statement or card app. Do not say that no matching transaction exists; say only that the request cannot be progressed with the details provided."
  +"CARD_NOT_FOUND"  |  -  |  -  |  -  |  -  |  =>  |  "ESCALATE_RECORD_NOT_FOUND"  |  "Internal note for the case handler (never sent to the customer). MiVision found the card but eChamps did not; the two systems disagree. Check the account number and the card manually."
  +-  |  -  |  -  |  -  |  -  |  =>  |  "ESCALATE_RECORD_NOT_FOUND"  |  "Internal note for the case handler (never sent to the customer). The not-found reason is null or not recognised. Review manually."
  ```

---

## `dmn/required-triage-fields.dmn`

**Decision ids**

- v2 only: `RequiredTriageFields` — "Required Triage Fields"
- v3 only: `RequiredTriageFields_V3` — "Required Triage Fields"

---

## `dmn/triage-routing-v2.dmn` → `dmn/triage-routing-v3.dmn`

**Decision ids**

- v2 only: `TriageRoutingV2` — "Triage Routing V2"
- v3 only: `TriageRouting_V3` — "Triage Routing V2"

---

## `forms/escalation-review.form`

- form id: `hsbc-escalation-review` → `hsbc-escalation-review-v3`

---

## `forms/fraud-response-review.form`

- form id: `hsbc-fraud-response-review` → `hsbc-fraud-response-review-v3`

---

## `forms/locate-record.form`

- form id: `hsbc-locate-record` → `hsbc-locate-record-v3`

---

## `forms/mentor-approval-v2.form` → `forms/mentor-approval-v3.form`

- form id: `hsbc-mentor-approval-v2` → `hsbc-mentor-approval-v3`

**Fields added in v3**

- `Text_FraudSummary` (text) — `**What the fraud team said:** {{fraudTeamSummary}}`
    - `conditional` = `{"hide": "=get or else(fraudTeamSummary, \"\") = \"\""}`

---

## `forms/request-handover.form`

- form id: `hsbc-request-handover` → `hsbc-request-handover-v3`

---

## Files with no semantic differences

