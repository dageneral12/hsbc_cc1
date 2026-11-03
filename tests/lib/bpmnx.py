"""Extract every FEEL expression out of the BPMN models (never retyped).

Each Expr has: file, process, element (id), kind, target (a name for inputs/outputs), text.
"""
import glob
import os
import re
import xml.etree.ElementTree as ET
from collections import namedtuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROCESS_DIR = os.path.join(ROOT, "process")
B = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
Z = "{http://camunda.org/schema/zeebe/1.0}"

Expr = namedtuple("Expr", "file process element kind target text")

KEYWORDS = {
    "if", "then", "else", "and", "or", "not", "true", "false", "null", "in", "for", "return", "some",
    "every", "satisfies", "between", "instance", "of", "function", "is", "defined", "count", "contains",
}
MULTIWORD_FUNCS = [
    "get or else", "list contains", "string join", "substring after", "substring before", "upper case",
    "lower case", "string length", "is defined", "is empty", "starts with", "ends with", "date and time",
    "get value", "get entries", "put all", "list replace", "index of", "distinct values", "append",
]


def bpmn_files():
    return sorted(glob.glob(os.path.join(PROCESS_DIR, "*.bpmn")))


def _is_expr(v):
    return isinstance(v, str) and v.startswith("=")


def extract(path):
    root = ET.parse(path).getroot()
    proc = root.find(B + "process")
    pid = proc.get("id")
    fname = os.path.basename(path)
    out = []
    # map every extension element up to its owning BPMN element id
    def walk(el, owner):
        tag = el.tag.split("}")[-1]
        if el.get("id") and el.tag.startswith(B):
            owner = el.get("id")
        if el.tag == B + "conditionExpression" and el.text and el.text.strip():
            out.append(Expr(fname, pid, owner, "condition", None, el.text.strip()))
        elif el.tag in (B + "timeDuration", B + "timeCycle", B + "timeDate") and el.text and _is_expr(el.text.strip()):
            out.append(Expr(fname, pid, owner, "timer", tag, el.text.strip()))
        elif el.tag == Z + "input" and _is_expr(el.get("source")):
            out.append(Expr(fname, pid, owner, "input", el.get("target"), el.get("source")))
        elif el.tag == Z + "output" and _is_expr(el.get("source")):
            out.append(Expr(fname, pid, owner, "output", el.get("target"), el.get("source")))
        elif el.tag == Z + "script" and _is_expr(el.get("expression")):
            out.append(Expr(fname, pid, owner, "script", el.get("resultVariable"), el.get("expression")))
        elif el.tag == Z + "property" and _is_expr(el.get("value")):
            out.append(Expr(fname, pid, owner, "property", el.get("name"), el.get("value")))
        elif el.tag == Z + "header" and _is_expr(el.get("value")):
            out.append(Expr(fname, pid, owner, "header", el.get("key"), el.get("value")))
        elif el.tag == Z + "subscription" and _is_expr(el.get("correlationKey")):
            out.append(Expr(fname, pid, owner, "correlationKey", None, el.get("correlationKey")))
        elif el.tag == Z + "taskDefinition":
            for a, v in el.attrib.items():
                if _is_expr(v):
                    out.append(Expr(fname, pid, owner, "jobType", a, v))
        elif el.tag == Z + "adHoc":
            for a in ("outputElement", "outputCollection", "activeElementsCollection"):
                if _is_expr(el.get(a)):
                    out.append(Expr(fname, pid, owner, "adhoc", a, el.get(a)))
        elif el.tag == Z + "loopCharacteristics":
            for a, v in el.attrib.items():
                if _is_expr(v):
                    out.append(Expr(fname, pid, owner, "loop", a, v))
        elif el.tag == Z + "assignmentDefinition":
            for a, v in el.attrib.items():
                if _is_expr(v):
                    out.append(Expr(fname, pid, owner, "assignment", a, v))
        elif el.tag == Z + "taskSchedule":
            for a, v in el.attrib.items():
                if _is_expr(v):
                    out.append(Expr(fname, pid, owner, "taskSchedule", a, v))
        elif el.tag == B + "completionCondition" and el.text and el.text.strip():
            out.append(Expr(fname, pid, owner, "completionCondition", None, el.text.strip()))
        for c in el:
            walk(c, owner)
    walk(proc, pid)
    # activation conditions on ad-hoc children (zeebe:property or attributes named activationCondition)
    for el in proc.iter():
        v = el.get("activationCondition")
        if v and _is_expr(v):
            out.append(Expr(fname, pid, el.get("id"), "activationCondition", None, v))
    return out


def all_expressions():
    res = []
    for f in bpmn_files():
        res.extend(extract(f))
    return res


def gateways(path):
    """{gateway_id: {'default': flow_id|None, 'flows': [(flow_id, target, name, condition|None)]}}"""
    root = ET.parse(path).getroot()
    proc = root.find(B + "process")
    gws = {}
    for g in proc.iter(B + "exclusiveGateway"):
        gws[g.get("id")] = {"default": g.get("default"), "flows": []}
    for f in proc.iter(B + "sequenceFlow"):
        s = f.get("sourceRef")
        if s in gws:
            c = f.find(B + "conditionExpression")
            gws[s]["flows"].append((f.get("id"), f.get("targetRef"), f.get("name"),
                                    c.text.strip() if c is not None and c.text else None))
    return gws


def element_ids(path):
    """All (kind, id, name) of reportable element types for the coverage tool."""
    root = ET.parse(path).getroot()
    proc = root.find(B + "process")
    return proc.get("id"), proc


def strip_strings(expr):
    return re.sub(r'"(?:[^"\\]|\\.)*"', '""', expr)


def free_variables(expr):
    """Heuristic: root identifiers an expression reads (locals defined as context keys before use are dropped)."""
    s = strip_strings(expr)
    for m in MULTIWORD_FUNCS:
        s = s.replace(m, " ")
    loop_vars = set(re.findall(r"\b(?:for|some|every)\s+([A-Za-z_]\w*)\s+in\b", s))
    seen, names, local = set(), [], set()
    for m in re.finditer(r"(?<![\w.\]\)])([A-Za-z_]\w*)(?!\w)(\s*\()?(\s*:)?", s):
        n, call, key = m.group(1), m.group(2), m.group(3)
        if call or n in KEYWORDS or n in loop_vars:
            continue
        if key:
            if n not in seen:
                local.add(n)
            seen.add(n)
            continue
        if n in local:
            continue
        seen.add(n)
        if n not in names:
            names.append(n)
    return sorted(names)
