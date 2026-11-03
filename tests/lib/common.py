"""Shared helpers: c8ctl wrapper, FEEL evaluation, REST client, reporter. Python stdlib only."""
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENV_FILE = os.path.join(ROOT, "newcluster2", "newClient222-env.sh")
REPORT_DIR = os.path.join(ROOT, "tests", "reports")
PROFILE = "hsbc-cards"
UA = {"User-Agent": "hsbc-cards-test-suite/1.0"}


# --------------------------------------------------------------------------- c8ctl
def _json_values(out):
    dec, vals, i = json.JSONDecoder(), [], 0
    while i < len(out):
        if out[i] in "[{":
            try:
                o, j = dec.raw_decode(out, i)
                vals.append(o)
                i = j
                continue
            except ValueError:
                pass
        i += 1
    return vals


def c8(*args, profile=PROFILE, timeout=120):
    """Run c8ctl with --json. Returns (returncode, [json values found], raw output)."""
    try:
        r = subprocess.run(["c8ctl", *args, "--profile", profile, "--json"], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, [], "timeout"
    return r.returncode, _json_values(r.stdout), r.stdout


def feel(expr, variables=None, profile=PROFILE):
    """Evaluate on the cluster with `c8ctl feel evaluate`. Returns dict(ok, result, warnings, error)."""
    args = ["feel", "evaluate", expr if expr.startswith("=") else "=" + expr]
    if variables:
        args += ["--vars", json.dumps(variables)]
    last = None
    for attempt in range(5):  # cluster round trip flakes occasionally (playbook s15)
        rc, vals, raw = c8(*args, profile=profile)
        d = next((v for v in vals if isinstance(v, dict)), None)
        if rc == 0 and d and "result" in d:
            return {"ok": True, "result": d["result"], "warnings": [w.get("message", "") for w in d.get("warnings", [])], "error": None}
        last = (d or {}).get("message") or raw.strip()[:300]
        if d and "Failed to parse" in str(last):
            break  # deterministic, no retry
        time.sleep(2 + attempt * 2 if "Authentication" in str(last) else 1)
    return {"ok": False, "result": None, "warnings": [], "error": last}


# --------------------------------------------------------------------------- env + REST
def load_env(path=ENV_FILE):
    """Parse line by line, never source. Values are never printed."""
    env = {}
    if not os.path.exists(path):
        raise SystemExit("cluster env file not found: " + path)
    with open(path) as fh:
        for line in fh:
            m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line.rstrip("\n"))
            if m:
                env[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return env


class Rest:
    """Orchestration Cluster REST (OAuth client credentials), token cached and refreshed."""

    def __init__(self):
        self.env = load_env()
        self.base = self.env["ZEEBE_REST_ADDRESS"].rstrip("/")
        self._tok = None
        self._exp = 0
        self._lock = threading.Lock()

    def token(self):
        with self._lock:
            if self._tok and time.time() < self._exp - 60:
                return self._tok
            data = urllib.parse.urlencode({
                "grant_type": "client_credentials", "client_id": self.env["CAMUNDA_CLIENT_ID"],
                "client_secret": self.env["CAMUNDA_CLIENT_SECRET"], "audience": "zeebe.camunda.io"}).encode()
            out = json.load(urllib.request.urlopen(urllib.request.Request(self.env["CAMUNDA_OAUTH_URL"], data, UA), timeout=30))
            self._tok = out["access_token"]
            self._exp = time.time() + int(out.get("expires_in", 300))
            return self._tok

    def post(self, path, body, retries=3):
        last = None
        for i in range(retries):
            req = urllib.request.Request(self.base + path, json.dumps(body).encode(), {
                **UA, "Authorization": "Bearer " + self.token(), "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    raw = r.read()
                    return 200, (json.loads(raw) if raw else {})
            except urllib.error.HTTPError as e:
                raw = e.read()
                try:
                    payload = json.loads(raw)
                except ValueError:
                    payload = {"raw": raw[:300].decode("utf8", "replace")}
                if e.code in (429, 500, 502, 503, 504) and i < retries - 1:
                    time.sleep(1 + i)
                    last = (e.code, payload)
                    continue
                return e.code, payload
            except (urllib.error.URLError, TimeoutError) as e:
                last = (0, {"error": str(e)})
                time.sleep(1 + i)
        return last

    def get(self, path):
        req = urllib.request.Request(self.base + path, headers={**UA, "Authorization": "Bearer " + self.token()})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return 200, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, {}
        except (urllib.error.URLError, TimeoutError):
            return 0, {}

    def search(self, kind, filt=None, limit=500):
        code, out = self.post("/v2/%s/search" % kind, {"filter": filt or {}, "page": {"limit": limit}})
        return (out or {}).get("items", []) if code == 200 else []


# --------------------------------------------------------------------------- reporting
class Reporter:
    def __init__(self, suite):
        self.suite = suite
        self.rows = []
        self._lock = threading.Lock()

    def _add(self, status, cid, msg):
        with self._lock:
            self.rows.append({"status": status, "id": cid, "msg": msg})

    def ok(self, cid, msg=""):
        self._add("PASS", cid, msg)

    def fail(self, cid, msg):
        self._add("FAIL", cid, msg)

    def warn(self, cid, msg):
        self._add("WARN", cid, msg)

    def skip(self, cid, msg):
        self._add("SKIP", cid, msg)

    def check(self, cid, cond, msg_fail, msg_ok=""):
        (self.ok if cond else self.fail)(cid, msg_ok if cond else msg_fail)
        return cond

    def counts(self):
        c = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
        for r in self.rows:
            c[r["status"]] += 1
        return c

    def summary(self, show_warn=True, max_lines=400):
        c = self.counts()
        shown = 0
        for r in self.rows:
            if r["status"] == "FAIL" or (show_warn and r["status"] == "WARN"):
                if shown < max_lines:
                    print("  %-4s %s :: %s" % (r["status"], r["id"], r["msg"]))
                shown += 1
        if shown > max_lines:
            print("  ... %d more (see report json)" % (shown - max_lines))
        print("[%s] pass=%d fail=%d warn=%d skip=%d" % (self.suite, c["PASS"], c["FAIL"], c["WARN"], c["SKIP"]))
        os.makedirs(REPORT_DIR, exist_ok=True)
        with open(os.path.join(REPORT_DIR, self.suite + ".json"), "w") as fh:
            json.dump({"suite": self.suite, "counts": c, "rows": self.rows}, fh, indent=1)
        return c["FAIL"] == 0


def match(expected, actual):
    """Subset match. dict -> every key must match; {'$re': pattern}; {'$in': [..]}; {'$any': True}; lists exact."""
    if isinstance(expected, dict):
        if "$re" in expected:
            return isinstance(actual, str) and re.fullmatch(expected["$re"], actual, re.S) is not None
        if "$in" in expected:
            return actual in expected["$in"]
        if "$contains" in expected:
            return isinstance(actual, str) and expected["$contains"] in actual
        if "$notnull" in expected:
            return actual is not None
        if not isinstance(actual, dict):
            return False
        return all(k in actual and match(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(match(e, a) for e, a in zip(expected, actual))
    if isinstance(expected, float) or isinstance(actual, float):
        try:
            return abs(float(expected) - float(actual)) < 1e-9
        except (TypeError, ValueError):
            return False
    return expected == actual
