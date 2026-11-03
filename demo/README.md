# Demo emails

One command per scenario. Each script drops an email, unread, into the demo inbox, as if the customer had sent it. The email listener starts the case within about 20 seconds. Mailbox details come from `clusterInfo/connectors.env` and are never printed.

Before each scenario, select the matching scenario on the simulator home page: `S2` for the fraud case, `S6` for all others.

| Command | Scenario | Simulator | Expected outcome |
|---|---|---|---|
| `demo/s1-no-card.sh` | S1 no card details | S6 | Email asks for the card number |
| `demo/s2-incomplete-card.sh` | S2 incomplete card number | S6 | Email asks for all 16 digits |
| `demo/s3-other-company.sh` | S3 card of another company | S6 | Email asks the customer to check the card |
| `demo/s4-cvv.sh` | S4 incorrect CVV | S6 | CVV retry advice, then RESOLVED |
| `demo/s5-unauthorised.sh` | S5 unauthorised sender | S6 | Notice to the authorised contact |
| `demo/s6-fraud.sh` | S6 fraud alert | S2 | Email to the fraud team; the case waits |
| `demo/s7-two-requests.sh` | S7 two requests in one email | S6 | Escalation task, no customer email |
| `demo/screenshot.sh` | Pasted screenshot only | S6 | Agent reads the image (needs the local RPA worker) |

Follow-ups:

- `demo/reply.sh <caseId> "<text>"` sends a customer reply as Jasmin. Example: `demo/reply.sh HSBC-DCL-20261030095031743 "The full card number is 5550410099018801."`
- `demo/fraud-reply.sh <caseId> keep|remove` sends a fraud team reply. You can also pass your own text in quotes instead of `keep` or `remove`.

Options for any command:

- `--dry-run` prints the email instead of sending it.
- `--image FILE` adds a picture pasted into the body.
- `--attach` sends that picture as a normal attachment instead.

To list all scenarios, run `python3 demo/send_demo_email.py list`.

Notes:

- **Where outbound email goes:** demo mode sends every outbound email, including the fraud team email, to the `demoEmailRedirect` address.
- **Replying from a mail client:** you can reply straight from your mail client instead of using `reply.sh` or `fraud-reply.sh`. Keep the `[HSBC-DCL-n]` or `[HSBC-FRD-n]` tag in the subject. In demo mode, replies are accepted from any sender.
- **Read emails are skipped:** the listener only picks up unread mail. Don't open the demo inbox in a mail client while presenting.
- **Your own address:** an email sent to the inbox from your own address starts the S5 unauthorised-sender route.
