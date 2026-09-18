"""One place for the model behind every text a customer reads (auto-replies, drafts, outreach, chat widget, VA previews).
Sep 17 2026: back on gpt-5.2. GPT-5.6 Sol drafted bland one-liners that ignored the thread ("Let me pull the numbers and get right
back to you" to a customer who just named a budget and a Saturday) and took 3-5 s per draft, tripping the 10 s suggestion timeout
into canned fallbacks. gpt-5.2 uses the specifics and answers in about a second."""

CUSTOMER_TEXT_MODEL = ("openai", "gpt-5.2")
JESSI_CHAT_MODEL = CUSTOMER_TEXT_MODEL  # the typed Ask Jessi window: same brain as her texts
