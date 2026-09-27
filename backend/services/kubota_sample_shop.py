"""One finished, graded Kubota sales shop for the Kubota Demo account, so the demo has a real scorecard and report to show.
Content only; services.mystery_shops.ensure_kubota_sample_shop writes it (idempotent, seed_key)."""

SEED_KEY = "kubota_sample_shop"

PERSON = {"name": "Tyler Brandt", "phone": "+15005550199", "email": "", "department": "eq_sales", "title": "Equipment Sales", "notes": "Sample person for the Kubota demo. Replace with a real rep before you shop anyone."}

PERSONA = {"name": "Randy Coker", "voice": "male", "opening_line": "I've got about 12 acres and I'm trying to figure out what I need."}

CURVEBALLS = ["Mention the John Deere dealer down the road showed you something similar", "You have a trade you do not mention until they ask"]

TURNS = [
    {"role": "rep", "text": "Thanks for calling Mountain West Kubota, this is Tyler. How can I help you today?"},
    {"role": "customer", "text": "Hey Tyler. I've got about 12 acres and I'm trying to figure out what I need."},
    {"role": "rep", "text": "Happy to help with that. Can I get your name first?"},
    {"role": "customer", "text": "Randy. Randy Coker."},
    {"role": "rep", "text": "Good to meet you, Randy. Before we talk machines, tell me what you're trying to get done out there. What does the property look like and what are the main jobs?"},
    {"role": "customer", "text": "It's mostly pasture with some brush along the fence lines. I need to keep it mowed, and I've got a quarter-mile gravel driveway that washes out every spring."},
    {"role": "rep", "text": "So brush hogging the pasture and keeping that driveway graded. Is the ground pretty flat, or are you working slopes?"},
    {"role": "customer", "text": "Mostly flat, one hill on the back side. Nothing crazy."},
    {"role": "rep", "text": "Got it. How often do you figure you'll be on the machine? Every weekend in the summer, or more of a once-a-month thing?"},
    {"role": "customer", "text": "Probably every other weekend spring through fall, and I'd like to move some snow in the winter."},
    {"role": "rep", "text": "That's real use. What are you running now, and what's not working about it?"},
    {"role": "customer", "text": "An old Ford 8N my dad left me. No loader, no power steering, and it's getting hard to start. I'd probably trade it if that's worth anything."},
    {"role": "rep", "text": "We can absolutely look at the 8N as a trade. Sounds like a loader is a must for you, plus a rotary cutter for the pasture and a box blade or rear blade for that driveway. Anything else you'd want to hook up?"},
    {"role": "customer", "text": "A snow blade or blower for the winter. That's about it."},
    {"role": "rep", "text": "Perfect. Based on 12 acres, brush, gravel and snow, you're right in the L Series compact range, something like an L2502 or L3302 with a loader. The reason I'd steer you there instead of a sub-compact is the driveway: you want the weight and the hydraulics to pull a loaded box blade without spinning, and the operator station is a lot more comfortable when you're out there for four hours."},
    {"role": "customer", "text": "Okay. I'll be honest, the Deere dealer down the road showed me a 3025E and it was a little cheaper."},
    {"role": "rep", "text": "That's a good machine and it's fair to compare them. Where the L Series usually wins for a property like yours is the hydrostatic transmission with the HST Plus, the loader lift capacity, and how many of these we service locally, which matters when you're in the middle of hay season. I'd rather you run both and feel the difference than take my word for it."},
    {"role": "customer", "text": "That's fair. What's the price on the L3302?"},
    {"role": "rep", "text": "With the loader and the implements we talked about it'll land somewhere in the low forties before your trade, and there's zero percent financing on the L Series right now. I'd like to get you on one first, then put real numbers together with the 8N in the deal. Could you come out Saturday morning? I'll have an L3302 with a box blade hooked up and we can put it on our gravel lot."},
    {"role": "customer", "text": "Saturday works. Ten o'clock?"},
    {"role": "rep", "text": "Ten o'clock Saturday, you and me and an L3302. What's the best cell number for you, Randy, so I can text you a reminder and directions?"},
    {"role": "customer", "text": "Eight oh one, five five five, oh one nine nine."},
    {"role": "rep", "text": "Got it. Bring a couple photos of the 8N if you can and I'll have a trade number ready. See you Saturday at ten, Randy."},
    {"role": "customer", "text": "Sounds good, Tyler. Thanks."},
]

# criterion ids are stable so the report's per-criterion pass rates line up across seeds
RESULTS = [
    {"criterion_id": "eqs01", "text": "Answered with their name and the dealership, got and used the customer's name", "critical": False, "weight": 1, "passed": True,
     "evidence": "Thanks for calling Mountain West Kubota, this is Tyler ... Good to meet you, Randy."},
    {"criterion_id": "eqs02", "text": "Discovery: asked what the customer is trying to accomplish before recommending anything", "critical": True, "weight": 3, "passed": True,
     "evidence": "Before we talk machines, tell me what you're trying to get done out there."},
    {"criterion_id": "eqs03", "text": "Application: asked where it will run, terrain, acreage or site, material, hours of use", "critical": False, "weight": 2, "passed": True,
     "evidence": "Is the ground pretty flat, or are you working slopes? ... How often do you figure you'll be on the machine?"},
    {"criterion_id": "eqs04", "text": "Asked what they own now and what is not working about it, plus attachments or implements needed", "critical": False, "weight": 2, "passed": True,
     "evidence": "What are you running now, and what's not working about it? ... Anything else you'd want to hook up?"},
    {"criterion_id": "eqs05", "text": "Asked about timing, trade, transportation or storage limits and other brands being considered", "critical": False, "weight": 2, "passed": False,
     "evidence": "The trade came up because Randy offered it and the Deere comparison came from Randy. Tyler never asked about transportation, storage or timing."},
    {"criterion_id": "eqs06", "text": "Connected features to the customer's application (productivity, reliability, operator experience) instead of listing specs", "critical": False, "weight": 2, "passed": True,
     "evidence": "You want the weight and the hydraulics to pull a loaded box blade without spinning, and the operator station is a lot more comfortable when you're out there for four hours."},
    {"criterion_id": "eqs07", "text": "Handled objections (price, Deere, used unit, size) honestly without bashing competitors", "critical": False, "weight": 2, "passed": True,
     "evidence": "That's a good machine and it's fair to compare them ... I'd rather you run both and feel the difference."},
    {"criterion_id": "eqs08", "text": "Set a specific next step: appointment, demo, walk-around, test drive, trade evaluation or quote with a real time", "critical": True, "weight": 3, "passed": True,
     "evidence": "Could you come out Saturday morning? ... Ten o'clock Saturday, you and me and an L3302."},
    {"criterion_id": "eqs09", "text": "Got the customer's phone number and recapped what happens next", "critical": True, "weight": 1, "passed": True,
     "evidence": "What's the best cell number for you, Randy ... Bring a couple photos of the 8N and I'll have a trade number ready. See you Saturday at ten."},
]

SCORE_PCT = 88  # 16 weight points, eqs05 (2) missed

SUMMARY = ("Tyler answered with the dealership and his name, got Randy's name early and used it, and did real discovery before naming a machine: the jobs, the terrain, "
           "how often it runs, the current 8N and the implements needed. He landed on the L Series for the right reasons and tied the recommendation to the gravel driveway "
           "and long days on the seat instead of reading specs. The Deere 3025E objection was handled with respect, and he closed on a specific Saturday 10 AM demo with the "
           "machine and implement Randy will actually use, then got the cell number and recapped. The gap: the trade and the Deere comparison only surfaced because Randy brought them up, "
           "and transportation, storage and timing were never asked.")

WINS = ["Discovery before the recommendation: jobs, terrain, hours and current equipment all came before the L Series was mentioned",
        "Tied the L3302 to Randy's driveway and comfort on long days rather than listing horsepower",
        "Closed on a real time (Saturday 10 AM) with the exact machine and implement, and got the best cell number"]

COACHING = ["Ask about the trade, timing and other brands yourself instead of waiting for the customer to volunteer them: 'Is there anything you'd trade in?' and 'What else have you looked at?'",
            "Add one transportation and storage question every time: 'How will it get home, and where will it live?' It changes the loader and tire recommendation",
            "Offer two demo times instead of one so the customer picks rather than decides"]

ADHERENCE = {"score_pct": 85,
             "hits": ["Asks what the customer is trying to accomplish before recommending any machine", "Asks where the equipment will operate: acreage, terrain, site or material",
                      "Asks how often and how many hours it will be used", "Asks what implements or attachments they need", "Asks what they own now and what does or does not work about it",
                      "Connects features to the customer's application (productivity, reliability, operator experience) instead of listing specs", "Handles objections honestly without bashing competitors",
                      "Sets a specific next step with a real day and time (visit, demo, walk-around, trade evaluation, quote)", "Gets the customer's name and best phone number and recaps"],
             "misses": ["Asks about transportation, storage or property limitations", "Asks what other brands or machines they are considering", "Asks who will operate it and when they need it"],
             "coaching": ["Work transportation, storage and 'who else are you looking at' into discovery before the recommendation"],
             "summary": "Followed the Kubota Sales Practice Call closely: discovery first, application-based recommendation, honest objection handling and a firm demo. Three discovery questions were skipped."}
