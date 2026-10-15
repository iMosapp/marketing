"""Every outbound text must go through services.twilio_service.send_sms (the central send gate: billing lock, STOP, consent,
sender policy, disclosure, send ledger) and declare its purpose. Static AST scan of the backend (tests excluded):
- every send_sms(...) passes purpose=...; a literal purpose is one of outbound_gate.PURPOSES;
- purpose="system" also passes a literal system_kind listed in outbound_gate.SYSTEM_KINDS;
- the only Twilio messages.create(...) call is the one inside services/twilio_service.py."""
import ast
import pathlib

from services.outbound_gate import PURPOSES, SYSTEM_KINDS

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKIP_DIRS = {"tests", "venv", ".venv", "__pycache__", "scripts"}
SENDERS = {"send_sms", "send_mms", "_ss"}


def _files():
    for p in ROOT.rglob("*.py"):
        if not SKIP_DIRS.intersection(p.relative_to(ROOT).parts):
            yield p


def _name(fn):
    return fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""


def inventory():
    missing, bad, direct, count = [], [], [], 0
    for p in _files():
        tree = ast.parse(p.read_text(), filename=str(p))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _name(node.func)
            where = f"{p.relative_to(ROOT)}:{node.lineno}"
            if name in SENDERS:
                count += 1
                kws = {k.arg: k.value for k in node.keywords}
                pv = kws.get("purpose")
                if pv is None:
                    missing.append(where)
                    continue
                if isinstance(pv, ast.Constant):
                    if pv.value not in PURPOSES:
                        bad.append(f"{where} purpose={pv.value!r}")
                    elif pv.value == "system":
                        sk = kws.get("system_kind")
                        if not (isinstance(sk, ast.Constant) and sk.value in SYSTEM_KINDS):
                            bad.append(f"{where} system text without an approved system_kind")
            elif name == "create" and isinstance(node.func, ast.Attribute) and _name(node.func.value) == "messages" \
                    and not str(p).endswith("services/twilio_service.py"):
                direct.append(where)
    return missing, bad, direct, count


def test_every_send_declares_a_purpose_and_goes_through_the_gate():
    missing, bad, direct, count = inventory()
    assert count >= 40, f"expected the full send inventory, found {count} send_sms calls"
    assert not missing, f"send_sms without purpose=: {missing}"
    assert not bad, f"send_sms with an unapproved purpose / system kind: {bad}"
    assert not direct, f"Twilio messages.create outside the gate: {direct}"


def test_gate_is_called_inside_send_sms():
    src = (ROOT / "services" / "twilio_service.py").read_text()
    body = src.split("async def send_sms(", 1)[1].split("\nasync def ", 1)[0]
    assert "outbound_gate.evaluate(" in body and "send_ledger.claim(" in body and "_deliver(" in body
    assert body.index("outbound_gate.evaluate(") < body.index("_deliver(")


if __name__ == "__main__":
    m, b, d, n = inventory()
    print(f"{n} send_sms calls")
    print("missing purpose:", *m, sep="\n  ")
    print("bad purpose:", *b, sep="\n  ")
    print("direct messages.create calls:", *d, sep="\n  ")
