"""Every outbound text must go through services.twilio_service.send_sms (the dealership guard) and say who is sending: a from-number,
the sending user's id, or platform=True for IMOS's own notifications. Static AST scan of the backend (tests excluded)."""
import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKIP_DIRS = {"tests", "venv", ".venv", "__pycache__"}
SENDERS = {"send_sms", "send_mms"}


def _files():
    for p in ROOT.rglob("*.py"):
        if not SKIP_DIRS.intersection(p.relative_to(ROOT).parts):
            yield p


def _name(fn):
    return fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""


def inventory():
    unattributed, direct = [], []
    for p in _files():
        tree = ast.parse(p.read_text(), filename=str(p))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _name(node.func)
            where = f"{p.relative_to(ROOT)}:{node.lineno}"
            if name in SENDERS:
                kws = {k.arg: k.value for k in node.keywords}
                platform = isinstance(kws.get("platform"), ast.Constant) and kws["platform"].value is True
                if not (len(node.args) >= 4 or "from_phone" in kws or "user_id" in kws or platform):
                    unattributed.append(where)
            elif name == "create" and isinstance(node.func, ast.Attribute) and _name(node.func.value) == "messages" \
                    and not str(p).endswith("services/twilio_service.py"):
                direct.append(where)
    return unattributed, direct


@pytest.mark.xfail(reason="send paths are wired to the guard in the Phase 2 wiring step (after the Stripe live deploy)", strict=False)
def test_every_send_is_attributed_and_guarded():
    unattributed, direct = inventory()
    assert not unattributed, f"send_sms without from_phone / user_id / platform=True: {unattributed}"
    assert not direct, f"Twilio messages.create outside the guard: {direct}"


if __name__ == "__main__":
    u, d = inventory()
    print("unattributed send_sms calls:", *u, sep="\n  ")
    print("direct messages.create calls:", *d, sep="\n  ")
