#!/usr/bin/env python3
"""Drop a demo email into the HSBC demo inbox, as if the customer (or the fraud team) had sent it.

The email is appended UNREAD to INBOX over IMAP, so the email listener picks it up within about 20 seconds.
Mailbox details are read from newcluster2/connectors.env and are never printed.

Usage (from anywhere):
  python3 demo/send_demo_email.py list
  python3 demo/send_demo_email.py <scenario> [--image FILE] [--attach] [--dry-run]
  python3 demo/send_demo_email.py reply <caseId> "<reply text>" [--image FILE] [--attach]
  python3 demo/send_demo_email.py fraud-reply <caseId> keep|remove|"<free text>"

<caseId> is the HSBC-DCL-... id shown in Operate (variable caseId) or in the subject of the email the case sent.
--image adds a picture pasted into the body (inline, read by the inline-image RPA step; needs the local RPA worker);
with --attach it is a normal attachment instead (no RPA worker needed).
"""
import argparse, email.utils, imaplib, mimetypes, os, re, sys, time
from email.message import EmailMessage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(ROOT, "newcluster2", "connectors.env")
DOMAIN = "burjkhalifahtravel.ae"
JASMIN = ("Jasmin Al Rashid", "jasmin@" + DOMAIN)
SARA = ("Sara Al Hashimi", "sara@" + DOMAIN)
UNKNOWN = ("Accounts Payable", "accounts@external-sender.example")
FRAUD_TEAM = ("Card Fraud Team", "fraud-team@bank-demo.example")
SIGN_J = "\n\nKind regards,\nJasmin Al Rashid\nBurj Khalifah Travel LLC"

# simulator = scenario to select on the simulator home page before sending (eChamps data follows it)
SCENARIOS = {
    "s1-no-card": dict(
        title="S1 No card details", sender=JASMIN, simulator="S6",
        subject="[HSBC-CARDS] Corporate card declined at Emaar Malls",
        body="Hi team,\n\nOne of our corporate cards was declined at Emaar Malls on 22 June 2026 for AED 620.00. "
             "Can you tell us why?" + SIGN_J,
        expect="Missing card details: a Mentor-approved email asks for the full card number.",
        next="Reply with the card: reply <caseId> \"The card number is 5550410099018801.\""),
    "s2-incomplete-card": dict(
        title="S2 Incomplete card number", sender=SARA, simulator="S6",
        subject="[HSBC-CARDS] Company card declined",
        body="Hello,\n\nOur card 5550 4100 9901 was declined at Emaar Malls on 22 June 2026 for AED 620.00. "
             "Please advise.\n\nKind regards,\nSara Al Hashimi\nBurj Khalifah Travel LLC",
        expect="Incomplete card number: a Mentor-approved email asks for all 16 digits.",
        next="Reply: reply <caseId> \"The full card number is 5550410099018801.\" -> CVV advice -> RESOLVED"),
    "s3-other-company": dict(
        title="S3 Card of a different company", sender=JASMIN, simulator="S6",
        subject="[HSBC-CARDS] Company card declined",
        body="Hello,\n\nOur card 4111 1111 1111 1111 was declined at Emaar Malls on 22 June 2026 for AED 620.00. "
             "Can you help?" + SIGN_J,
        expect="Card not found for this client: a Mentor-approved email asks the customer to check the card.",
        next="Do nothing to show CLOSED_NO_RESPONSE after customerReplySla (P3D on email starts), or reply with 5550410099018801."),
    "s4-cvv": dict(
        title="S4 Incorrect CVV", sender=JASMIN, simulator="S6",
        subject="[HSBC-CARDS] Card declined at Emaar Malls",
        body="Hello,\n\nOur card 5550410099018801 was declined at Emaar Malls on 22 June 2026 for AED 620.00. "
             "Could you tell us why?" + SIGN_J,
        expect="eChamps decline 0076 (CVV): Mentor approves the CVV retry advice -> RESOLVED.",
        next="Approve the Mentor task in Tasklist; the customer email arrives in your mailbox (demo redirect)."),
    "s5-unauthorised": dict(
        title="S5 Unauthorised sender", sender=UNKNOWN, simulator="S6",
        subject="[HSBC-CARDS] Declined card",
        body="Hi,\n\nCard 5550410099018801 of Burj Khalifah Travel was declined at Emaar Malls on 22 June 2026 "
             "for AED 620.00. Please unblock it.\n\nThanks,\nAccounts Payable",
        expect="UNAUTHORISED_SENDER: a notice goes to the authorised contact (Jasmin); no card data is asked from the sender.",
        next="Approve the Mentor task. (Sending from your own mailbox gives the same route.)"),
    "s6-fraud": dict(
        title="S6 Fraud alert", sender=JASMIN, simulator="S2",
        subject="[HSBC-CARDS] Card declined overseas",
        body="Hello,\n\nOur card 5550410099013821 was declined at Atlas Hotel Singapore on 1 July 2026 for AED 2,150.00. "
             "Please check urgently." + SIGN_J,
        expect="eChamps 0713 FALC: email to the fraud team tagged [HSBC-FRD-n], then the case waits.",
        next="Reply to the fraud email from your mailbox (keep the subject), or: fraud-reply <caseId> keep|remove"),
    "s7-two-requests": dict(
        title="S7 Two requests in one email", sender=JASMIN, simulator="S6",
        subject="[HSBC-CARDS] Two cards declined",
        body="Hello,\n\nTwo of our company cards were declined. Card 5550410099018801 was declined at Emaar Malls on "
             "22 June 2026 for AED 620.00. Separately, card 5550410099013821 was declined at Atlas Hotel Singapore on "
             "1 July 2026 for AED 2,150.00. Please help with both." + SIGN_J,
        expect="Guardrail: two requests -> escalation task for a person (rule 18); no customer email.",
        next="Open the escalation task in Tasklist."),
    "screenshot": dict(
        title="Screenshot only (inline image)", sender=JASMIN, simulator="S6", image="emailImage/HSBC Mobile Banking Transaction Declined.png",
        subject="[HSBC-CARDS] Card declined - see screenshot",
        body="Hi team,\n\nOne of our cards was declined, see the screenshot from the app below. Could you tell us why?" + SIGN_J,
        expect="The agent reads card, amount and merchant from the screenshot. This screenshot has no date and does not "
               "match the simulator, so the case asks for the missing details.",
        next="Needs the local RPA worker running. Reply with the date, or use a screenshot showing AED 620.00 / Emaar Malls / 22/06/2026."),
}


def load_env():
    env = {}
    with open(ENV_FILE) as f:
        for line in f:
            m = re.match(r"\s*(?:export\s+)?(\w+)=['\"]?(.*?)['\"]?\s*$", line)
            if m:
                env[m.group(1)] = m.group(2)
    missing = [k for k in ("INBOUND_MAIL_ADDRESS", "INBOUND_MAIL_SERVER", "INBOUND_MAIL_USER", "INBOUND_MAIL_PASSWORD") if not env.get(k)]
    if missing:
        sys.exit("connectors.env is missing: " + ", ".join(missing))
    return env


def case_number(case_id):
    m = re.search(r"(\d{6,})", case_id)
    if not m:
        sys.exit("caseId should look like HSBC-DCL-20261030095031743")
    return m.group(1)


def build(env, sender, subject, body, image=None, attach=False, in_reply_to=None):
    msg = EmailMessage()
    msg["From"] = email.utils.formataddr(sender)
    msg["To"] = env["INBOUND_MAIL_ADDRESS"]
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=False)
    msg["Message-ID"] = email.utils.make_msgid(idstring="demo%d" % int(time.time()), domain=sender[1].split("@")[1])
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    msg.set_content(body)
    if image:
        path = image if os.path.isabs(image) else os.path.join(ROOT, image)
        data = open(path, "rb").read()
        ctype = mimetypes.guess_type(path)[0] or "image/png"
        maintype, subtype = ctype.split("/", 1)
        fname = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(path))
        if attach:
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=fname)
        else:
            cid = email.utils.make_msgid(domain=sender[1].split("@")[1])
            html = "".join("<p>%s</p>" % p.replace("\n", "<br>") for p in body.split("\n\n"))
            parts = html.split("</p>", 1)  # picture after the first paragraph, like a pasted screenshot
            html = parts[0] + "</p><p><img src=\"cid:%s\" width=\"320\"></p>" % cid[1:-1] + (parts[1] if len(parts) > 1 else "")
            msg.add_alternative(html, subtype="html")
            msg.get_payload()[1].add_related(data, maintype=maintype, subtype=subtype, cid=cid, filename=fname, disposition="inline")
    return msg


def deliver(env, msg, dry_run):
    if dry_run:
        print("--- dry run, not sent ---")
        print("From: %s\nSubject: %s\n\n%s" % (msg["From"], msg["Subject"], (msg.get_body(("plain",)) or msg).get_content()))
        return
    imap = imaplib.IMAP4_SSL(env["INBOUND_MAIL_SERVER"], int(env.get("INBOUND_MAIL_IMAP_PORT") or 993))
    try:
        imap.login(env["INBOUND_MAIL_USER"], env["INBOUND_MAIL_PASSWORD"])
        status, _ = imap.append("INBOX", None, imaplib.Time2Internaldate(time.time()), msg.as_bytes())  # no \Seen flag: stays unread
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    if status != "OK":
        sys.exit("IMAP append failed: " + status)
    print("Delivered to the demo inbox (unread): %s\n  From: %s" % (msg["Subject"], msg["From"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", help="list | <scenario> | reply | fraud-reply")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--image", help="picture to include (default: the scenario's own, if any)")
    ap.add_argument("--attach", action="store_true", help="send the picture as a normal attachment instead of inline")
    ap.add_argument("--dry-run", action="store_true", help="print the email instead of delivering it")
    a = ap.parse_args()

    if a.command == "list":
        for key, s in SCENARIOS.items():
            print("%-20s %-32s simulator %s  from %s" % (key, s["title"], s["simulator"], s["sender"][1]))
        return

    env = load_env()
    if a.command == "reply":
        if len(a.args) != 2:
            sys.exit('usage: reply <caseId> "<reply text>"')
        n = case_number(a.args[0])
        msg = build(env, JASMIN, "RE: [HSBC-CARDS] Card declined [HSBC-DCL-%s]" % n, a.args[1] + SIGN_J,
                    a.image, a.attach, in_reply_to="<case-HSBC-DCL-%s@demo>" % n)
        deliver(env, msg, a.dry_run)
        print("The case re-triages with the reply within about a minute.")
        return

    if a.command == "fraud-reply":
        if len(a.args) != 2:
            sys.exit("usage: fraud-reply <caseId> keep|remove|\"<free text>\"")
        n = case_number(a.args[0])
        text = {"keep": "The card must stay blocked and be reissued: the card details appear to have been exposed.",
                "remove": "Block removed. The transaction is genuine and the card can be used again."}.get(a.args[1].lower(), a.args[1])
        msg = build(env, FRAUD_TEAM, "RE: Fraud review needed [HSBC-FRD-%s]" % n,
                    text + "\n\nRegards,\nCard Fraud Team", in_reply_to="<fraud-HSBC-FRD-%s@demo>" % n)
        deliver(env, msg, a.dry_run)
        print("The fraud process interprets the reply, then a Mentor task prepares the customer email.")
        return

    s = SCENARIOS.get(a.command)
    if not s:
        sys.exit("Unknown scenario '%s'. Run: python3 demo/send_demo_email.py list" % a.command)
    print("%s\n  Before sending: select simulator scenario %s on the simulator home page." % (s["title"], s["simulator"]))
    msg = build(env, s["sender"], s["subject"], s["body"], a.image or s.get("image"), a.attach)
    deliver(env, msg, a.dry_run)
    print("  Expect: %s\n  Next:   %s" % (s["expect"], s["next"]))


if __name__ == "__main__":
    main()
