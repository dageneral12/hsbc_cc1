#!/usr/bin/env python3
"""Static checks (playbook s15 layers 1 and 2), offline except for the lint plugin:

  - `c8ctl bpmn lint` on every BPMN
  - cross-file references resolve: calledElement -> process id, calledDecision -> decision id, formId -> form id,
    linkedResource -> .rpa id (all with the deployment binding the models use)
  - registry check: every job type in every model is served by something real (an OOTB connector, the AI agent
    job worker, or the RPA worker label expression). A type that nothing serves hangs the instance with no incident.
  - orphans: DMN/forms/RPA resources that no model references
"""
import glob
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from tests.lib import bpmnx, common  # noqa: E402

Z, B = bpmnx.Z, bpmnx.B
D = "{https://www.omg.org/spec/DMN/20191111/MODEL/}"
CONNECTOR_TYPE = re.compile(r"^io\.camunda(\.agenticai)?:[A-Za-z0-9._-]+:\d+$")


def main():
    rep = common.Reporter("static")
    pdir = bpmnx.PROCESS_DIR
    procs, decisions, forms, rpas = {}, {}, {}, {}
    for f in bpmnx.bpmn_files():
        procs[ET.parse(f).getroot().find(B + "process").get("id")] = os.path.basename(f)
    for f in glob.glob(os.path.join(pdir, "dmn", "*.dmn")):
        for d in ET.parse(f).getroot().iter(D + "decision"):
            decisions[d.get("id")] = os.path.basename(f)
    for f in glob.glob(os.path.join(pdir, "forms", "*.form")):
        forms[json.load(open(f))["id"]] = os.path.basename(f)
    for f in glob.glob(os.path.join(pdir, "rpa", "*.rpa")):
        rpas[json.load(open(f))["id"]] = os.path.basename(f)

    used = {"decision": set(), "form": set(), "rpa": set(), "process": set()}
    for f in bpmnx.bpmn_files():
        name = os.path.basename(f)
        rc, _v, raw = common.c8("bpmn", "lint", f, "--quiet")
        # the plugin prints findings and exits non-zero on errors
        rep.check("lint %s" % name, rc == 0, "c8ctl bpmn lint exit %d: %s" % (rc, raw.strip()[:300]))
        root = ET.parse(f).getroot()
        for el in root.iter():
            tag = el.tag.split("}")[-1]
            if tag == "calledElement":
                pid = el.get("processId")
                used["process"].add(pid)
                rep.check("ref %s calledElement %s" % (name, pid), pid in procs, "no process with this id in process/")
                if el.get("bindingType") != "deployment":
                    rep.warn("ref %s calledElement %s" % (name, pid), "bindingType is %s, not deployment" % el.get("bindingType"))
            elif tag == "calledDecision":
                did = el.get("decisionId")
                used["decision"].add(did)
                rep.check("ref %s calledDecision %s" % (name, did), did in decisions, "no decision with this id in process/dmn")
            elif tag == "formDefinition":
                fid = el.get("formId")
                if fid:
                    used["form"].add(fid)
                    rep.check("ref %s formId %s" % (name, fid), fid in forms, "no form with this id in process/forms")
            elif tag == "linkedResource":
                rid = el.get("resourceId")
                used["rpa"].add(rid)
                rep.check("ref %s linkedResource %s" % (name, rid), rid in rpas, "no .rpa with this id in process/rpa")
            elif tag == "taskDefinition":
                t = el.get("type") or ""
                if t.startswith("="):
                    ok = "camunda::RPA-Task::" in t
                    rep.check("registry %s %s job type (expression)" % (name, el.get("id") or ""), ok, "dynamic job type is not the RPA worker label pattern: %s" % t[:80])
                else:
                    rep.check("registry %s job type %s" % (name, t), bool(CONNECTOR_TYPE.match(t)),
                              "job type is not an OOTB connector / agent worker type; no worker is registered for it")
    for kind, have, label in (("decision", decisions, "DMN decision"), ("form", forms, "form"), ("rpa", rpas, "RPA script")):
        for i, fn in sorted(have.items()):
            if i not in used[kind]:
                rep.warn("orphan %s %s" % (label, i), "%s is not referenced by any BPMN" % fn)
    ok = rep.summary()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
