"""A Bill never gets a woman's voice: gender comes from name / label / pronouns, 'older' and 'young' are age flavours only."""
import os
import pytest
from collections import Counter
from bson import ObjectId
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from services import persona_gender as pg  # noqa: E402
from services import live_shops as ls  # noqa: E402
from services import locales as loc  # noqa: E402
from services import mystery_shops as ms  # noqa: E402
from services.kubota_pack import KUBOTA_CHALLENGES, KUBOTA_SCENARIOS, roll_persona  # noqa: E402
from routers.database import get_db  # noqa: E402

pytestmark = pytest.mark.asyncio


def test_gender_resolution_order():
    assert pg.gender_of({"name": "Bill Harmon", "voice": "older"}) == "male"
    assert pg.gender_of({"name": "Janet Kowalski", "voice": "older"}) == "female"
    assert pg.gender_of({"name": "Tyler Brooks", "voice": "young"}) == "male"
    assert pg.gender_of({"name": "Leslie Park", "voice": "older", "summary": "57, retired, her son wants to come too"}) == "female"
    assert pg.gender_of({"name": "Leslie Park", "voice": "older", "summary": "57, retired, his son wants to come too"}) == "male"
    assert pg.gender_of({"name": "Xq Zzz", "voice": "older"}) == "female"  # nothing to go on
    assert pg.gender_of({"name": "Bill Harmon", "gender": "female"}) == "female"  # explicit always wins
    assert pg.describe({"name": "Bill Harmon", "voice": "older"}) == "an older man"
    assert pg.describe({"name": "Kelly Nguyen", "summary": "26, first time buying"}) == "a young woman"


def test_live_voice_pool_follows_gender():
    sid = ObjectId()
    v_bill = ls.voice_for({"_id": sid, "persona": {"name": "Bill Harmon", "voice": "older"}})
    v_janet = ls.voice_for({"_id": sid, "persona": {"name": "Janet Kowalski", "voice": "older"}})
    assert v_bill in ls.MASCULINE and v_janet in ls.FEMININE
    assert ls.voice_for({"_id": sid, "persona": {"name": "Tyler Brooks", "voice": "young"}}) in ls.MASCULINE
    assert ls.voice_for({"_id": sid, "locale": "en-GB", "persona": {"name": "Harold Finch", "voice": "older"}}) in ls.UK_VOICES["male"]


def test_relay_label_never_turns_a_man_female():
    assert pg.voice_label({"name": "Bill Harmon", "voice": "older"}) == "male"
    assert pg.voice_label({"name": "Janet Kowalski", "voice": "older"}) == "older"
    assert loc.relay_voice("en-US", pg.voice_label({"name": "Bill Harmon", "voice": "older"})) == loc.relay_voice("en-US", "male")


def test_kubota_masters_roll_a_voice_that_matches_the_name():
    for c in KUBOTA_CHALLENGES[:4]:
        for _ in range(200):
            p = roll_persona(c["persona"])
            g = pg.first_name_gender(p["name"])
            assert g is None or p["gender"] == g, p["name"]
            assert p["voice"] in ("young", "older") or p["voice"] == p["gender"]
    labels = Counter(c["persona"]["voice"] for c in KUBOTA_SCENARIOS)
    assert set(labels) == {"female", "male"}
    assert all(pg.first_name_gender(c["persona"]["name"]) in (None, c["persona"]["voice"]) for c in KUBOTA_SCENARIOS)
    assert pg.gender_of({"name": "Bill Harmon", "voice": "female"}) == "male"  # a slipped label loses to an unambiguous name


def test_draft_normalizer_writes_gender():
    d = ms.normalize_draft({"title": "Sales caller: x", "body": "Answer well.", "persona": {"name": "Walt Brennan", "voice": "older", "opening_line": "Hi"}}, "sales")
    assert d["persona"]["gender"] == "male" and d["persona"]["voice"] == "older"
    d2 = ms.normalize_draft({"title": "Sales caller: y", "body": "Answer well.", "persona": {"name": "Walt Brennan", "voice": "older", "gender": "male"}}, "sales")
    assert d2["persona"]["gender"] == "male"


async def test_library_backfill_leaves_no_persona_without_gender():
    db = get_db()
    await ms.ensure_challenges(db)
    assert await db.scripts.count_documents({"pool": "mystery_shop", "persona": {"$exists": True}, "persona.gender": {"$exists": False}}) == 0
    bill = await db.scripts.find_one({"pool": "mystery_shop", "persona.name": "Bill Harmon"}, {"persona": 1})
    assert bill and bill["persona"]["gender"] == "male"
