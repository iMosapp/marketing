"""Website widget chat pacing: kb.pace setting + the human typing / split logic in the rendered script."""
import json
import shutil
import subprocess

import pytest

from services import widget_js
from services.widgets import normalize_config, public_config


def _w(kb):
    return {"_id": "x", "key": "TESTKEY1", "kb": kb}


def test_pace_defaults_and_validation():
    assert normalize_config(_w({}))["kb"]["pace"] == "natural"
    assert normalize_config(_w({"pace": "relaxed"}))["kb"]["pace"] == "relaxed"
    assert normalize_config(_w({"pace": "instant"}))["kb"]["pace"] == "instant"
    assert normalize_config(_w({"pace": "warp"}))["kb"]["pace"] == "natural"


def test_public_config_exposes_pace():
    assert public_config(_w({"pace": "relaxed"}), {"name": "S"})["chat_pace"] == "relaxed"
    assert public_config(_w({}), {"name": "S"})["chat_pace"] == "natural"


SAMPLES = [
    "Hi! Sure thing.",
    "i'M On Social is the Relationship OS for sales teams. It tells each rep who to talk to today and why, drafts the text in their voice, "
    "and remembers every customer detail. Pricing depends on team size, most stores start with a founding partner pilot. Want me to grab you a quick demo time?",
    "Plans start at $39.99 per rep a month. That includes:\n- A business number per rep\n- Jessi AI replies\n- The digital card and reviews\n\n"
    "Teams of 10 or more get volume pricing. We also run a 90-day founding partner pilot for new stores, which includes setup and training at no extra cost. "
    "Mr. Smith on our team handles those, he is in Mon to Fri from 9 a.m. Eastern. Want me to set up a call with him?",
]


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
@pytest.mark.parametrize("pace", ["natural", "relaxed", "instant"])
def test_split_reply_in_rendered_script(pace, tmp_path):
    js = widget_js.render({"chat_pace": pace, "appearance": {}, "doors": {}, "copy": {}})
    a = js.index("var PACES")
    e = js.index("\n}\n", js.index("function splitReply")) + 3
    f = tmp_path / "split.js"
    f.write_text("var C = " + json.dumps({"chat_pace": pace}) + ";\n" + js[a:e] +
                 "\nconsole.log(JSON.stringify(" + json.dumps(SAMPLES) + ".map(function(t){ return { parts: splitReply(t), ms: typeMs(t) }; })));")
    out = json.loads(subprocess.run(["node", str(f)], capture_output=True, text=True, check=True).stdout)
    short, mid, long_ = out
    assert short["parts"] == [SAMPLES[0]]
    if pace == "instant":
        assert all(len(o["parts"]) == 1 for o in out) and all(o["ms"] == 0 for o in out)
        return
    assert len(mid["parts"]) == 2 and len(long_["parts"]) == 3
    for o, src in zip(out, SAMPLES):
        assert " ".join(p.replace("\n\n", " ") for p in o["parts"]).replace("\n", " ").split() == src.replace("\n", " ").split()
    assert "$39.99" in long_["parts"][0] and "- Jessi AI replies" in long_["parts"][0]  # list kept whole, decimal not split
    assert any(p.startswith("Mr. Smith") for p in long_["parts"]) or any("Mr. Smith" in p for p in long_["parts"])
    assert all(len(p) >= 40 for p in long_["parts"])
    cap = 7000 if pace == "natural" else 14000
    assert 0 < mid["ms"] <= cap
