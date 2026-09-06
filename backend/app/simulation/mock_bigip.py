"""A local mock BIG-IP object store that replays a plan's generated REST
calls in order and reports what a real device's iControl REST API would
plausibly accept or reject.

Closes a real gap: every generated tmsh/REST/AS3/Ansible output in this
tool is verified for *internal consistency* (all four formats derive from
the same resolved plan) and *correctness against parsed real data*, but
none of it has ever actually been applied to a live or lab BIG-IP. This
replay engine catches the class of error that only shows up when commands
actually run in order against real state -- a duplicate create, a POST
that references an object the plan hasn't created yet (an ordering bug in
generation, which this exists specifically to catch), a PATCH aimed at
something that was never there to begin with.

This is explicitly a simulation against a small set of realistic rules,
not a certification -- it cannot catch a real device's licensing checks,
platform-specific validation, or anything about the physical/virtual
hardware. It closes the "was this ever tested" gap partway, not all the
way; a real dry run against a lab device is still the only complete
answer.
"""
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.generation.rest_generator import RestCall


class SimulationStep(BaseModel):
    step: int
    method: str
    path: str
    name: str
    outcome: str  # "ok" | "error"
    message: str


class SimulationResult(BaseModel):
    steps: List[SimulationStep]
    total: int
    succeeded: int
    failed: int
    overall: str  # "PASS" | "FAILED"


def _collection_key(path: str) -> str:
    """`/mgmt/tm/ltm/node` -> "ltm/node". Every `/mgmt/tm/ltm/monitor/<type>`
    path folds into one "ltm/monitor" collection -- the type suffix on a
    monitor POST is which kind, not a distinct namespace; a real device
    enforces unique monitor names across all types the same way."""
    parts = [p for p in path.split("/") if p]
    rest = parts[2:]  # drop "mgmt", "tm"
    if len(rest) >= 2 and rest[0] == "ltm" and rest[1] == "monitor":
        return "ltm/monitor"
    return "/".join(rest[:2])


def _member_node_names(members: List[Dict[str, Any]]) -> List[str]:
    names = []
    for m in members:
        raw = m.get("name", "")
        names.append(raw.rsplit(":", 1)[0] if ":" in raw else raw)
    return names


_TARGET_NAME_RE = re.compile(r"/([^/]+)$")


def _decode_target_name(path: str) -> str:
    match = _TARGET_NAME_RE.search(path)
    raw = match.group(1) if match else path
    return raw.replace("~", "/")


def simulate(rest_calls: List[RestCall], seed: Optional[Dict[str, Dict[str, Any]]] = None) -> SimulationResult:
    state: Dict[str, Dict[str, Any]] = {k: dict(v) for k, v in (seed or {}).items()}

    def exists(collection: str, name: str) -> bool:
        return name in state.get(collection, {})

    steps: List[SimulationStep] = []
    for i, call in enumerate(rest_calls, start=1):
        collection = _collection_key(call.path)
        name = call.body.get("name") or _decode_target_name(call.path)
        outcome, message = "ok", "would succeed"

        if call.method == "POST":
            if exists(collection, name):
                outcome, message = "error", "object already exists on target -- duplicate create"
            elif collection == "ltm/pool":
                missing = [n for n in _member_node_names(call.body.get("members", [])) if not exists("ltm/node", n)]
                if missing:
                    outcome, message = "error", "references node(s) not yet created: %s" % ", ".join(missing)
            elif collection == "ltm/virtual":
                pool = call.body.get("pool")
                if pool and not exists("ltm/pool", pool):
                    outcome, message = "error", "references pool not yet created: %s" % pool
            elif collection == "net/self":
                vlan = call.body.get("vlan")
                if vlan and not exists("net/vlan", vlan):
                    outcome, message = "error", "references VLAN not yet created: %s" % vlan
            elif collection == "net/route-domain":
                missing = [v for v in call.body.get("vlans", []) if not exists("net/vlan", v)]
                if missing:
                    outcome, message = "error", "references VLAN(s) not yet created: %s" % ", ".join(missing)
            if outcome == "ok":
                state.setdefault(collection, {})[name] = call.body

        elif call.method in ("PATCH", "PUT"):
            target = _decode_target_name(call.path)
            if not exists(collection, target):
                outcome, message = "error", "target object not found -- must already exist on the device before this plan runs"
            else:
                state[collection][target] = {**state[collection][target], **call.body}

        elif call.method == "DELETE":
            target = _decode_target_name(call.path)
            if not exists(collection, target):
                outcome, message = "error", "target object not found"
            else:
                del state[collection][target]

        steps.append(SimulationStep(step=i, method=call.method, path=call.path, name=name, outcome=outcome, message=message))

    succeeded = sum(1 for s in steps if s.outcome == "ok")
    failed = len(steps) - succeeded
    return SimulationResult(steps=steps, total=len(steps), succeeded=succeeded, failed=failed, overall="PASS" if failed == 0 else "FAILED")
