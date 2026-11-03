#!/usr/bin/env python3
"""Which model elements has no HSBC process instance ever reached? (playbook s15 layer 9)

"It deploys and it lints" says nothing about whether a branch has ever run. For every process in process/*.bpmn
this asks the engine for the activities, gateways, events and end events that no instance has reached.
Only HSBC_* process definitions are read. Nothing is created or changed.

Usage:  python3 -I tests/coverage.py [--json] [--min PCT]
Exit 0 only when every element has been reached (or, with --min, when coverage >= PCT for every process).
"""
import argparse
import glob
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from tests.lib import bpmnx, common  # noqa: E402

B = bpmnx.B
KINDS = (
    "serviceTask", "userTask", "scriptTask", "businessRuleTask", "manualTask", "sendTask", "receiveTask",
    "callActivity", "subProcess", "adHocSubProcess", "exclusiveGateway", "parallelGateway", "inclusiveGateway",
    "eventBasedGateway", "startEvent", "endEvent", "boundaryEvent", "intermediateCatchEvent", "intermediateThrowEvent",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="also write tests/reports/coverage.json")
    ap.add_argument("--min", type=float, default=100.0, help="required coverage percent per process (default 100)")
    args = ap.parse_args()
    rest = common.Rest()
    gap, report = False, {}
    for path in bpmnx.bpmn_files():
        proc = ET.parse(path).getroot().find(B + "process")
        pid = proc.get("id")
        if not pid.startswith("HSBC_"):
            continue
        declared = {e.get("id"): (e.tag.split("}")[-1], e.get("name") or "")
                    for e in proc.iter() if e.tag.split("}")[-1] in KINDS and e.get("id")}
        instances = rest.search("process-instances", {"processDefinitionId": pid}, 1000)
        reached = set()
        for inst in instances:
            for i in rest.search("element-instances", {"processInstanceKey": inst["processInstanceKey"]}, 1000):
                reached.add(i["elementId"])
        never = sorted((k, i, n) for i, (k, n) in declared.items() if i not in reached)
        covered = len(declared) - len(never)
        pct = covered / len(declared) * 100 if declared else 100.0
        states = {}
        for i in instances:
            states[i["state"]] = states.get(i["state"], 0) + 1
        print("\n%s\n  instances: %d  %s\n  coverage : %d/%d elements (%.0f%%)" % (pid, len(instances), states or "(none)", covered, len(declared), pct))
        if never:
            print("  never executed:")
            for k, i, n in never:
                print("    %-24s %-40s %s" % (k, i, n))
        if pct < args.min:
            gap = True
        report[pid] = {"instances": len(instances), "states": states, "covered": covered, "total": len(declared),
                       "never": [{"kind": k, "id": i, "name": n} for k, i, n in never]}
    print()
    if args.json:
        os.makedirs(common.REPORT_DIR, exist_ok=True)
        json.dump(report, open(os.path.join(common.REPORT_DIR, "coverage.json"), "w"), indent=1)
    return 1 if gap else 0


if __name__ == "__main__":
    sys.exit(main())
