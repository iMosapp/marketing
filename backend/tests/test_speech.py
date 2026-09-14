"""TTS verbalizer: numbers come out the way a person says them on the phone (mystery shops + practice calls)."""
from services.speech import NUMBERS_RULE, speakable


def test_money():
    assert speakable("The payment came out to 132.89 a month.") == "The payment came out to one hundred thirty-two dollars and eighty-nine cents a month."
    assert speakable("It is $132.89 with tax, or $1,299 down.") == "It is one hundred thirty-two dollars and eighty-nine cents with tax, or one thousand two hundred ninety-nine dollars down."
    assert speakable("$0.50, $45k, $2M, $1, $1.05") == "fifty cents, forty-five thousand dollars, two million dollars, one dollar, one dollar and five cents"


def test_phone_numbers():
    out = speakable("Call me at (435) 275-9829 or 435.275.9829 or 8015550142.")
    assert out.count("four three five, two seven five, nine eight two nine") == 2 and "eight zero one, five five five, zero one four two" in out


def test_years_miles_times_percent_ordinals():
    assert speakable("a 2022 Tahoe with 45,000 miles") == "a twenty twenty-two Tahoe with forty-five thousand miles"
    assert speakable("at 9:30 am, 4:05 pm or 10:00") == "at nine thirty AM, four oh five PM or ten o'clock"
    assert speakable("6.9% APR, 4.5 liters, 45k miles, the 3rd") == "six point nine percent APR, four point five liters, forty-five thousand miles, the third"
    assert speakable("2 minutes, 12 cars, 3 kids") == "two minutes, twelve cars, three kids"


def test_safe_and_idempotent():
    assert speakable("") == "" and speakable("No numbers here.") == "No numbers here."
    once = speakable("It is $132.89 on the 2022 model, call 435-275-9829.")
    assert speakable(once) == once and "$" not in once and not any(ch.isdigit() for ch in once)


def test_prompt_rule_mentions_the_examples():
    assert "a hundred and thirty-two dollars and eighty-nine cents" in NUMBERS_RULE and "phone number" in NUMBERS_RULE


def test_relay_twiml_speaks_the_opening_line():
    from services import scripts as scr
    from bson import ObjectId
    session = {"_id": ObjectId(), "token": "t" * 32, "persona": {"opening_line": "Hi, I saw the 2022 Tahoe for $32,500 online.", "voice": "female"}, "direction": "outbound", "store_name": "QA Motors"}
    xml = scr.relay_twiml(session)
    assert 'welcomeGreeting="Hi, I saw the twenty twenty-two Tahoe for thirty-two thousand five hundred dollars online."' in xml


def test_lead_whisper_reads_numbers_like_a_person():
    from services import lead_call_engine as eng
    job = {"lead": {"name": "Sarah Tester", "source_label": "Cars.com", "interest": "2022 Tahoe under $45,000", "comments": "Call me back at 435-275-9829 after 5:30 pm"}, "customer_phone": "+14352759829"}
    xml = eng.twiml_claimed_and_bridge(job, "+18015550100")
    assert "Interested in twenty twenty-two Tahoe under forty-five thousand dollars." in xml
    assert "four three five, two seven five, nine eight two nine after five thirty PM" in xml
    assert "<Dial" in xml and "+14352759829" in xml  # the number actually dialed is untouched
    assert "Press one to claim this lead" in eng.twiml_answer({"lead": {"source_label": "Cars.com"}}, "https://x/y")
