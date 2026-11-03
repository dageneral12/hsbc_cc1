#!/usr/bin/env python3
"""FEEL expression tests (playbook s15 layer 3).

Every expression is read out of process/*.bpmn with an XML parser and evaluated on the cluster with
`c8ctl feel evaluate --profile hsbc-cards`. Nothing is retyped. This suite needs no deployment.

  A. every conditional gateway: null / false / true / "null" / absent for each variable the condition reads
     (result must be a boolean: a non-boolean condition raises an incident in the engine)
  B. every branch of every routing gateway against an expected-flow table
  C. value tests (expected results) for scripts, activation conditions and correlation keys
  D. smoke + null matrix for every other expression (inputs, outputs, scripts, prompts, timers, headers)
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from tests.lib import bpmnx, common  # noqa: E402
from tests.expressions import cases  # noqa: E402

ABSENT = object()
BASE = cases.BASE


class Evaluator:
    def __init__(self, workers):
        self.pool = cf.ThreadPoolExecutor(max_workers=workers)
        self.cache = {}

    def run(self, jobs):
        """jobs: list of (expr, vars). Returns list of result dicts in order (cached)."""
        futs = []
        for expr, v in jobs:
            key = (expr, json.dumps(v, sort_keys=True))
            if key not in self.cache:
                self.cache[key] = self.pool.submit(common.feel, expr, v)
            futs.append(self.cache[key])
        return [f.result() for f in futs]

    def one(self, expr, v):
        return self.run([(expr, v)])[0]


def pick(expr, extra=None, override=None):
    names = bpmnx.free_variables(expr)
    v = {n: BASE[n] for n in names if n in BASE}
    if extra:
        v.update(extra)
    if override:
        v.update(override)
    return v


def variants(expr, v):
    """Yield (label, vars) for each null/false/true/"null"/absent substitution of every read variable,
    plus null for each dotted field that is read (communicationDraft.body etc.)."""
    names = [n for n in bpmnx.free_variables(expr) if n in v]
    for n in names:
        cur = v[n]
        # false/true are only meaningful substitutes for boolean (or structured) values; a string/number variable
        # never holds a boolean, so those two would only test a type mismatch that cannot occur.
        vals = [("null", None), ("false", False), ("true", True), ('"null"', "null"), ("absent", ABSENT)]
        if isinstance(cur, (str, int, float)) and not isinstance(cur, bool):
            vals = [x for x in vals if x[0] not in ("false", "true")]
        for label, val in vals:
            w = dict(v)
            if val is ABSENT:
                w.pop(n)
            else:
                w[n] = val
            yield "%s=%s" % (n, label), w
        if isinstance(v[n], dict):
            w = dict(v)
            w[n] = {}
            yield "%s={}" % n, w
            for fld in sorted(set(re.findall(r"(?<![\w.])%s\.([A-Za-z_]\w*)" % re.escape(n), bpmnx.strip_strings(expr)))):
                for label, val in (("null", None), ('"null"', "null")):
                    w = dict(v)
                    w[n] = dict(v[n])
                    w[n][fld] = val
                    yield "%s.%s=%s" % (n, fld, label), w


def eid(e):
    return "%s/%s [%s%s]" % (e.file, e.element, e.kind, (":" + e.target) if e.target else "")


def is_prompt(e):
    return e.kind == "input" and e.target and "rompt" in e.target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--quick", action="store_true", help="skip the null matrix for scripts/prompts (section D)")
    ap.add_argument("--only", help="substring filter on element id")
    args = ap.parse_args()
    rep = common.Reporter("expressions")
    common.feel("=1")  # warm up the CLI token before the parallel run
    ev = Evaluator(args.workers)

    exprs = bpmnx.all_expressions()
    index = {(e.process, e.element, e.kind, e.target): e for e in exprs}
    print("extracted %d expressions from %d BPMN files" % (len(exprs), len(bpmnx.bpmn_files())))

    # ---- A. gateway condition matrix -------------------------------------------------------------
    conds = [e for e in exprs if e.kind == "condition"]
    jobs, meta = [], []
    for e in conds:
        if args.only and args.only not in e.element:
            continue
        base = pick(e.text)
        for label, v in [("baseline", base)] + list(variants(e.text, base)):
            jobs.append((e.text, v))
            meta.append((e, label))
        # all referenced variables null together / absent together
        names = [n for n in bpmnx.free_variables(e.text) if n in base]
        if names:
            jobs.append((e.text, {k: (None if k in names else x) for k, x in base.items()}))
            meta.append((e, "all=null"))
            jobs.append((e.text, {k: x for k, x in base.items() if k not in names}))
            meta.append((e, "all=absent"))
    print("A. gateway condition matrix: %d evaluations" % len(jobs))
    bad = {}
    for (e, label), r in zip(meta, ev.run(jobs)):
        if not r["ok"]:
            bad.setdefault(e, []).append("%s -> ENGINE ERROR %s" % (label, r["error"]))
        elif not isinstance(r["result"], bool):
            bad.setdefault(e, []).append("%s -> %r (non-boolean: incident at runtime)" % (label, r["result"]))
    for e in conds:
        if args.only and args.only not in e.element:
            continue
        if e in bad:
            rep.fail("matrix %s" % eid(e), "; ".join(bad[e][:6]) + (" (+%d more)" % (len(bad[e]) - 6) if len(bad[e]) > 6 else ""))
        else:
            rep.ok("matrix %s" % eid(e))

    # ---- B. routing gateways ---------------------------------------------------------------------
    for path in bpmnx.bpmn_files():
        pid = os.path.basename(path)
        for gid, g in bpmnx.gateways(path).items():
            cond_flows = [f for f in g["flows"] if f[3]]
            if not cond_flows:
                continue
            if args.only and args.only not in gid:
                continue
            table = cases.ROUTING.get(gid)
            if not table:
                rep.fail("route %s/%s" % (pid, gid), "no routing cases for this gateway in tests/expressions/cases.py")
                continue
            flow_ids = {f[0] for f in g["flows"]}
            jobs, meta = [], []
            for row in table:
                name, over, expected = row[0], row[1], row[2]
                for fid, _t, _n, c in g["flows"]:
                    if c:
                        jobs.append((c, pick(c, override=over)))
                        meta.append((name, fid))
            res = ev.run(jobs)
            k = 0
            for row in table:
                name, over, expected = row[0], row[1], row[2]
                soft = row[3] if len(row) > 3 else None
                chosen, errs = None, []
                for fid, _t, _n, c in g["flows"]:
                    if not c:
                        continue
                    r = res[k]
                    k += 1
                    if not r["ok"] or not isinstance(r["result"], bool):
                        errs.append("%s -> %r" % (fid, r["result"] if r["ok"] else r["error"]))
                    elif r["result"] and chosen is None:
                        chosen = fid
                if chosen is None:
                    chosen = g["default"]
                cid = "route %s/%s :: %s" % (pid, gid, name)
                if expected not in flow_ids:
                    rep.fail(cid, "expected flow %s does not exist on the gateway (stale case table)" % expected)
                elif errs:
                    rep.fail(cid, "non-boolean condition: " + "; ".join(errs))
                elif chosen == expected:
                    rep.ok(cid)
                elif soft:
                    rep.warn(cid, "took %s, hardening expectation is %s: %s" % (chosen, expected, soft))
                else:
                    rep.fail(cid, "took %s, expected %s" % (chosen, expected))
    stale = set(cases.ROUTING) - {gid for p in bpmnx.bpmn_files() for gid in bpmnx.gateways(p)}
    for gid in sorted(stale):
        rep.fail("route %s" % gid, "case table for a gateway that no longer exists")

    # ---- script results first (outputs read them) ---------------------------------------------------
    scripts = [e for e in exprs if e.kind == "script"]
    sres = {}
    for e, r in zip(scripts, ev.run([(e.text, pick(e.text)) for e in scripts])):
        if r["ok"]:
            sres[e.element] = (e.target, r["result"])

    def ctx(e):
        extra = {}
        if e.element in sres:
            extra[sres[e.element][0]] = sres[e.element][1]
        return pick(e.text, extra=extra)

    # ---- C. value tests ----------------------------------------------------------------------------
    for key, rows in cases.VALUES.items():
        e = index.get(key)
        cid = "value %s/%s [%s:%s]" % (key[0], key[1], key[2], key[3])
        if e is None:
            rep.fail(cid, "expression not found in the BPMN (stale case table or the model changed)")
            continue
        for name, over, expected in rows:
            v = pick(e.text, override=over)
            r = ev.one(e.text, v)
            if not r["ok"]:
                rep.fail("%s :: %s" % (cid, name), "engine error: %s" % r["error"])
            elif common.match(expected, r["result"]):
                rep.ok("%s :: %s" % (cid, name))
            else:
                rep.fail("%s :: %s" % (cid, name), "got %s expected %s" % (json.dumps(r["result"])[:300], json.dumps(expected)[:200]))

    # ---- D. smoke + matrix for everything else ---------------------------------------------------
    rest = [e for e in exprs if e.kind != "condition" and (not args.only or args.only in e.element)]
    jobs = [(e.text, ctx(e)) for e in rest]
    print("D. smoke: %d expressions" % len(jobs))
    smoke = ev.run(jobs)
    unresolved = {}
    for e, r in zip(rest, smoke):
        if not r["ok"]:
            rep.fail("smoke %s" % eid(e), "engine error: %s" % r["error"])
            continue
        for w in r["warnings"]:
            m = re.search(r"No variable found with name '(\w+)'", w)
            if m:
                unresolved.setdefault(m.group(1), set()).add(e.element)
        if r["result"] is None and (e.kind == "script" or is_prompt(e)):
            rep.warn("smoke %s" % eid(e), "evaluated to null with a complete baseline")
        else:
            rep.ok("smoke %s" % eid(e))
    if not args.quick:
        mat = [e for e in rest if e.kind in ("script", "header", "property") or is_prompt(e) or e.kind in ("timer", "correlationKey")]
        jobs, meta = [], []
        for e in mat:
            base = ctx(e)
            for label, v in variants(e.text, base):
                jobs.append((e.text, v))
                meta.append((e, label))
        print("D. null matrix (scripts, prompts, inbound properties, timers): %d evaluations" % len(jobs))
        errs, nulls = {}, {}
        for (e, label), r in zip(meta, ev.run(jobs)):
            if not r["ok"]:
                errs.setdefault(e, []).append("%s -> %s" % (label, (r["error"] or "")[:120]))
            elif r["result"] is None and (e.kind == "script" or is_prompt(e)):
                nulls.setdefault(e, []).append(label)
        for e in mat:
            if e in errs:
                rep.fail("matrix %s" % eid(e), "; ".join(errs[e][:5]))
            elif e in nulls:
                rep.warn("matrix %s" % eid(e), "result becomes null when: " + ", ".join(nulls[e][:8]) + (" (+%d)" % (len(nulls[e]) - 8) if len(nulls[e]) > 8 else ""))
            else:
                rep.ok("matrix %s" % eid(e))

    # ---- variables read but not defined anywhere ---------------------------------------------------
    written = {e.target for e in exprs if e.kind in ("input", "output", "script") and e.target}
    written |= {k for k in BASE}
    for n, els in sorted(unresolved.items()):
        if n not in written and n not in {"toolCall"}:
            rep.warn("unresolved variable %s" % n, "read by %s but not in the case baseline and never mapped by a model" % ", ".join(sorted(els)[:4]))

    ok = rep.summary()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
