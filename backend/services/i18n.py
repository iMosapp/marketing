"""Client-facing strings in the client's language (proposal, kickoff, report PDF, GM emails, coaching digest).
Admin screens stay English until Phase E. Missing Dutch keys fall back to English, so nothing ever renders blank."""
from typing import Optional

T = {
    "en": {
        # proposal
        "prop.what.title": "What you get",
        "prop.what.body": "I'm On Social will mystery shop {client} by phone every month: {per} calls, placed by our AI caller at random times during your business hours. Every call is recorded, transcribed and graded against a phone skills scorecard and the scenario's success points, with written coaching for each person.",
        "prop.report.title": "Your report",
        "prop.report.body": "You receive a live store report (no login needed) plus a monthly PDF: who did well, who needs training, what the whole team misses most, and every call with its recording, transcript and coaching.",
        "prop.invest.title": "Investment",
        "prop.invest.body": "{price} per month, billed monthly by invoice (card or bank transfer) for an initial term of {term} months, then month to month. The first invoice is sent as soon as this proposal is signed and shops begin once it is paid.",
        "prop.part.title": "Your part",
        "prop.part.body": "Provide the names, cell numbers and department of the people to shop, your business hours, and a few real products or services our caller can reference. You confirm you have the right to have your staff's business calls recorded and evaluated for training, and that you have told them calls may be recorded.",
        "prop.cancel.title": "Cancel",
        "prop.cancel.body": "After the initial {term} month term, cancel any time with 30 days notice. Recordings and reports stay available to you for 12 months.",
        "prop.agree.title": "Agreement",
        "prop.agree.body": "By typing your name and signing below you agree to these terms on behalf of the store. This electronic signature is legally binding under the U.S. ESIGN Act.",
        "prop.notes.title": "Notes",
        # pdf
        "pdf.kicker": "I'M ON SOCIAL  |  MYSTERY SHOP REPORT",
        "pdf.completed": "Shops completed", "pdf.of": "{a} of {b}", "pdf.avg": "Average score", "pdf.people": "People shopped", "pdf.need": "Need training", "pdf.na": "n/a",
        "pdf.avg_short": "Avg {v}%", "pdf.no_scores": "No scores yet", "pdf.done": "{n} done", "pdf.scheduled_n": "{n} scheduled", "pdf.unreachable_n": "{n} unreachable", "pdf.planned_n": "{n} planned",
        "pdf.leaderboard": "{dept} leaderboard", "pdf.col.name": "NAME", "pdf.col.shops": "SHOPS", "pdf.col.avg": "AVG", "pdf.col.best": "BEST", "pdf.col.vs": "VS {prev}", "pdf.col.recognition": "RECOGNITION", "pdf.new": "new",
        "pdf.who": "Who did well, who needs another look", "pdf.col.dept": "DEPT", "pdf.col.crit": "CRIT MISSES", "pdf.col.status": "STATUS",
        "pdf.status.needs": "Needs training", "pdf.status.ok": "On track", "pdf.status.unreachable": "Unreachable", "pdf.status.scheduled": "Scheduled",
        "pdf.misses": "What {dept} misses most", "pdf.shops_n": "{n} shop", "pdf.shops_np": "{n} shops", "pdf.critical": "(critical)", "pdf.x_of_y": "{a} of {b}",
        "pdf.themes_dept": "Coaching themes for the next {dept} meeting", "pdf.themes": "Coaching themes for the next meeting", "pdf.mentioned": "mentioned {n}x",
        "pdf.every": "Every shop this month", "pdf.crit_misses": "Critical misses: ", "pdf.coaching": "Coaching: ", "pdf.unreachable_line": "Unreachable: {r}", "pdf.listen": "Listen / read: {url}",
        "badge.top_score": "Top score", "badge.most_improved": "Most improved", "badge.most_shops": "Most shops", "badge.top_score.detail": "{v}% on one call", "badge.most_improved.detail": "+{v} vs {prev}", "badge.most_shops.detail": "{n} shops",
        # monthly / weekly email
        "mail.month.subject": "{client}: your {month} mystery shop report",
        "mail.month.kicker": "I'M ON SOCIAL · MONTHLY MYSTERY SHOP REPORT", "mail.month.title": "{client}: {month}", "mail.hi": "Hi {name}, ", "mail.hi_generic": "Hi, ",
        "mail.month.intro": "here is your {month} mystery shop report. {line}",
        "mail.box.completed": "Shops completed", "mail.box.avg": "Average score", "mail.box.people": "People shopped", "mail.box.need": "Need training",
        "mail.leaderboard": "Leaderboard", "mail.top": "Top of the list", "mail.needs_training": "needs training",
        "mail.open_report": "Open the live report", "mail.pdf_attached": "The PDF version is attached. The live report has every call with its recording, transcript and coaching, and a history for each person.",
        "mail.footer": "I'm On Social LLC · 1741 Lunford Ln, Riverton, UT 84065 · You get this because you run mystery shops with us. Reply to this email to change who receives it.",
        "mail.week.subject": "{client}: this week's shops ({label})",
        "mail.week.kicker": "I'M ON SOCIAL · WEEKLY SHOP DIGEST", "mail.week.title": "{client}: {label}", "mail.week.intro": "here is what happened this week. {line}",
        "mail.week.none": "No shops were completed this week.",
        # proposal email to the GM
        "pmail.subject": "Mystery shop proposal for {client}",
        "pmail.title": "Phone mystery shop proposal for {client}", "pmail.hi": "Hi {name},",
        "pmail.body": "Here is the proposal we talked about: <b>{per}</b> mystery shops every month for <b>{price}/month</b>, with recordings, grades and a store report you can open any time.",
        "pmail.button": "Review and sign the proposal",
        "pmail.small": "Signing takes about a minute. Your first invoice arrives by email right after, and shops start once it is paid. Questions? Just reply to this email.",
        # scorecard text to the person who was shopped
        "sms.intro": "Hey {name}, that practice call just now was from I'm On Social{store}.", "sms.for": " for {store}", "sms.scored": "You scored {pct}%.", "sms.ready": "Your scorecard is ready.",
        "sms.nailed": "Nailed: {items}.", "sms.workon": "Work on: {items}.", "sms.link": "Full scorecard + recording: {url}",
        "sms.intro_text": "Hey {name}, those texts just now were a practice shop from I'm On Social{store}.", "sms.link_text": "Full scorecard + the thread: {url}",
        "prop.what.text": " Plus {per} text shops a month: our shopper texts the person like a real lead and we grade how fast and how well they reply.",
        "tx.under_min": "under a minute", "tx.h": "h", "tx.noreply.evidence": "No reply", "tx.first_after": "First reply after {d}", "tx.pace": "Slowest reply {d}, average {avg}",
        "tx.noreply.summary": "{name} never replied. The shopper texted at {time} and gave up after {hours} hours of silence. A real lead would have bought somewhere else.",
        "tx.noreply.coaching": "Answer every text lead within 5 minutes, even if it is only 'Got it, give me a few minutes and I will get you an answer.'",
        "sms.intro_email": "Hey {name}, that email thread just now was a practice shop from I'm On Social{store}.",
        "em.noreply.evidence": "No reply", "em.noreply.summary": "{name} never replied. The shopper emailed at {time} and gave up after {hours} hours of silence. A real internet lead would have bought somewhere else.",
        "em.noreply.coaching": "Answer every email lead within 30 minutes with a real reply, even if it is only 'Got your email, I am pulling the details and will have them to you within the hour.'",
        "sms.course": "{course}: {done} of {total} passed.", "sms.course_retry": " You need {need}% on this one, we will call again with it.",
        "vcf.sms": "Hi {name}, {sender} here with I'm On Social. {store} signed the team up for practice calls and scorecards from this number. Save it as a contact so you know it's us when we call: {url}",
        "vcf.note": "Practice calls and scorecard texts for {store} come from this number. I'm On Social.", "vcf.note_generic": "Practice calls and scorecard texts from I'm On Social come from this number.",
        "vcf.page_title": "Save {name} to your contacts", "vcf.page_body": "{store} signed the team up for practice calls. Every call and scorecard text comes from this number, so save it and you will always know it's us.",
        "vcf.page_body_generic": "Practice calls and scorecard texts come from this number. Save it and you will always know it's us.", "vcf.save": "Save contact", "vcf.hint": "iPhone: tap the file, then Create New Contact. Android: open with Contacts.",
        # summary lines
        "sum.none": "No shops were completed in {month}.",
        "sum.line": "{n} shop{s} completed in {month}{people}{avg}{need}",
        # digest (managers)
        "dig.subject": "{store}: coaching digest for {label}", "dig.kicker": "I'M ON SOCIAL · MONDAY COACHING DIGEST", "dig.morning": "Morning {name}. {line}",
        "dig.box.calls": "Calls graded", "dig.box.avg": "Team avg", "dig.box.crit": "Critical misses", "dig.box.unread": "Unread coaching",
        "dig.none": "No calls were graded last week. Recorded calls over 30 seconds are graded automatically when a scorecard applies.",
        "dig.open": "Open Team Call Scores", "dig.hint": "Tap any rep in the app to hear the calls and correct a grade. Reps tap \"Got it\" on their coaching, which is what \"unread\" counts.",
        "dig.footer": "You get this because you manage {store}. Turn it off under Team Call Scores in the app.", "dig.coach_on": "COACH {name} ON THIS", "dig.hit": "hit {a} of {b}", "dig.critical": "CRITICAL",
        "dig.perfect": "Hit every item on every graded call. Tell them.", "dig.first_week": "first graded week", "dig.vs": "{v} vs the week before", "dig.unread": "{n} coaching unread", "dig.read_all": "read all coaching",
        "dig.calls": "{n} call", "dig.calls_p": "{n} calls", "dig.best": "best {v}%", "dig.crit_n": "{n} critical miss", "dig.crit_np": "{n} critical misses", "dig.no_crit": "no critical misses",
    },
    "nl": {
        "prop.what.title": "Wat je krijgt",
        "prop.what.body": "I'm On Social belt {client} elke maand als mystery shopper: {per} gesprekken, op willekeurige momenten binnen jullie openingstijden, gevoerd door onze AI-beller. Elk gesprek wordt opgenomen, uitgeschreven en beoordeeld op een scorekaart voor telefoonvaardigheden plus de succespunten van het scenario, met schriftelijke coaching per medewerker.",
        "prop.report.title": "Jullie rapport",
        "prop.report.body": "Je krijgt een live vestigingsrapport (zonder inloggen) plus elke maand een pdf: wie het goed doet, wie training nodig heeft, wat het hele team het vaakst mist, en elk gesprek met opname, transcript en coaching.",
        "prop.invest.title": "Investering",
        "prop.invest.body": "{price} per maand, maandelijks gefactureerd (iDEAL, kaart of overboeking) voor een eerste termijn van {term} maanden, daarna per maand opzegbaar. De eerste factuur gaat direct na ondertekening uit en de shops starten zodra die betaald is.",
        "prop.part.title": "Jullie deel",
        "prop.part.body": "Geef de namen, mobiele nummers en afdeling van de medewerkers die we mogen bellen, jullie openingstijden en een paar echte auto's uit de voorraad die onze beller kan noemen. Je bevestigt dat jullie medewerkers zijn geïnformeerd dat zakelijke gesprekken opgenomen en beoordeeld kunnen worden voor training, en dat de ondernemingsraad hiermee heeft ingestemd waar dat verplicht is.",
        "prop.cancel.title": "Opzeggen",
        "prop.cancel.body": "Na de eerste termijn van {term} maanden kun je maandelijks opzeggen met 30 dagen opzegtermijn. Opnames en rapporten blijven 12 maanden beschikbaar.",
        "prop.agree.title": "Akkoord",
        "prop.agree.body": "Door je naam te typen en te ondertekenen ga je namens het bedrijf akkoord met deze voorwaarden. Deze elektronische handtekening is rechtsgeldig onder de eIDAS-verordening (EU) en het Nederlands recht.",
        "prop.notes.title": "Opmerkingen",
        "pdf.kicker": "I'M ON SOCIAL  |  MYSTERY SHOP RAPPORT",
        "pdf.completed": "Shops afgerond", "pdf.of": "{a} van {b}", "pdf.avg": "Gemiddelde score", "pdf.people": "Medewerkers gebeld", "pdf.need": "Training nodig", "pdf.na": "n.v.t.",
        "pdf.avg_short": "Gem. {v}%", "pdf.no_scores": "Nog geen scores", "pdf.done": "{n} afgerond", "pdf.scheduled_n": "{n} gepland", "pdf.unreachable_n": "{n} onbereikbaar", "pdf.planned_n": "{n} gepland",
        "pdf.leaderboard": "Ranglijst {dept}", "pdf.col.name": "NAAM", "pdf.col.shops": "SHOPS", "pdf.col.avg": "GEM.", "pdf.col.best": "BESTE", "pdf.col.vs": "T.O.V. {prev}", "pdf.col.recognition": "ERKENNING", "pdf.new": "nieuw",
        "pdf.who": "Wie het goed deed, wie aandacht nodig heeft", "pdf.col.dept": "AFD.", "pdf.col.crit": "KRIT. MISSERS", "pdf.col.status": "STATUS",
        "pdf.status.needs": "Training nodig", "pdf.status.ok": "Op koers", "pdf.status.unreachable": "Onbereikbaar", "pdf.status.scheduled": "Gepland",
        "pdf.misses": "Wat {dept} het vaakst mist", "pdf.shops_n": "{n} shop", "pdf.shops_np": "{n} shops", "pdf.critical": "(kritiek)", "pdf.x_of_y": "{a} van {b}",
        "pdf.themes_dept": "Coachingthema's voor het volgende {dept}-overleg", "pdf.themes": "Coachingthema's voor het volgende overleg", "pdf.mentioned": "{n}x genoemd",
        "pdf.every": "Alle shops deze maand", "pdf.crit_misses": "Kritieke missers: ", "pdf.coaching": "Coaching: ", "pdf.unreachable_line": "Onbereikbaar: {r}", "pdf.listen": "Luister / lees: {url}",
        "badge.top_score": "Hoogste score", "badge.most_improved": "Meest verbeterd", "badge.most_shops": "Meeste shops", "badge.top_score.detail": "{v}% in één gesprek", "badge.most_improved.detail": "+{v} t.o.v. {prev}", "badge.most_shops.detail": "{n} shops",
        "mail.month.subject": "{client}: jullie mystery shop rapport van {month}",
        "mail.month.kicker": "I'M ON SOCIAL · MAANDELIJKS MYSTERY SHOP RAPPORT", "mail.month.title": "{client}: {month}", "mail.hi": "Hoi {name}, ", "mail.hi_generic": "Hoi, ",
        "mail.month.intro": "hier is jullie mystery shop rapport van {month}. {line}",
        "mail.box.completed": "Shops afgerond", "mail.box.avg": "Gemiddelde score", "mail.box.people": "Medewerkers gebeld", "mail.box.need": "Training nodig",
        "mail.leaderboard": "Ranglijst", "mail.top": "Bovenaan", "mail.needs_training": "training nodig",
        "mail.open_report": "Open het live rapport", "mail.pdf_attached": "De pdf zit in de bijlage. In het live rapport staat elk gesprek met opname, transcript en coaching, plus de historie per medewerker.",
        "mail.footer": "I'm On Social LLC · 1741 Lunford Ln, Riverton, UT 84065 · Je ontvangt dit omdat jullie mystery shops bij ons afnemen. Beantwoord deze mail om de ontvanger te wijzigen.",
        "mail.week.subject": "{client}: de shops van deze week ({label})",
        "mail.week.kicker": "I'M ON SOCIAL · WEKELIJKS SHOP OVERZICHT", "mail.week.title": "{client}: {label}", "mail.week.intro": "dit gebeurde er deze week. {line}",
        "mail.week.none": "Er zijn deze week geen shops afgerond.",
        "pmail.subject": "Mystery shop voorstel voor {client}",
        "pmail.title": "Voorstel telefonische mystery shops voor {client}", "pmail.hi": "Hoi {name},",
        "pmail.body": "Hier is het voorstel waar we het over hadden: <b>{per}</b> mystery shops per maand voor <b>{price} per maand</b>, met opnames, beoordelingen en een vestigingsrapport dat je altijd kunt openen.",
        "pmail.button": "Bekijk en onderteken het voorstel",
        "pmail.small": "Ondertekenen duurt ongeveer een minuut. Je eerste factuur komt direct daarna per e-mail en de shops starten zodra die betaald is. Vragen? Beantwoord gewoon deze mail.",
        "sms.intro": "Hoi {name}, dat oefengesprek van net kwam van I'm On Social{store}.", "sms.for": " voor {store}", "sms.scored": "Je scoorde {pct}%.", "sms.ready": "Je scorekaart staat klaar.",
        "sms.nailed": "Goed gedaan: {items}.", "sms.workon": "Werk aan: {items}.", "sms.link": "Volledige scorekaart + opname: {url}",
        "sms.intro_text": "Hoi {name}, die berichten van net waren een oefenshop van I'm On Social{store}.", "sms.link_text": "Volledige scorekaart + het gesprek: {url}",
        "prop.what.text": " Plus {per} sms-shops per maand: onze shopper stuurt de medewerker een bericht zoals een echte lead en we beoordelen hoe snel en hoe goed die reageert.",
        "tx.under_min": "minder dan een minuut", "tx.h": "u", "tx.noreply.evidence": "Geen reactie", "tx.first_after": "Eerste reactie na {d}", "tx.pace": "Traagste reactie {d}, gemiddeld {avg}",
        "tx.noreply.summary": "{name} heeft niet gereageerd. De shopper stuurde om {time} een bericht en gaf het na {hours} uur stilte op. Een echte lead had ergens anders gekocht.",
        "tx.noreply.coaching": "Reageer binnen 5 minuten op elke lead die een bericht stuurt, al is het maar 'Ik kijk het even na, je hoort zo van me.'",
        "sms.intro_email": "Hoi {name}, die e-mailwissel van net was een oefenshop van I'm On Social{store}.",
        "em.noreply.evidence": "Geen reactie", "em.noreply.summary": "{name} heeft niet gereageerd. De shopper mailde om {time} en gaf het na {hours} uur stilte op. Een echte internetlead had ergens anders gekocht.",
        "em.noreply.coaching": "Reageer binnen 30 minuten op elke lead die mailt, al is het maar 'Je mail is binnen, ik zoek de details op en je hoort binnen een uur van me.'",
        "sms.course": "{course}: {done} van {total} gehaald.", "sms.course_retry": " Je hebt {need}% nodig op deze, we bellen er nog een keer mee.",
        "vcf.sms": "Hoi {name}, {sender} hier van I'm On Social. {store} heeft het team aangemeld voor oefengesprekken en scorekaarten vanaf dit nummer. Sla het op als contact, dan weet je dat wij het zijn als we bellen: {url}",
        "vcf.note": "Oefengesprekken en scorekaart-berichten voor {store} komen van dit nummer. I'm On Social.", "vcf.note_generic": "Oefengesprekken en scorekaart-berichten van I'm On Social komen van dit nummer.",
        "vcf.page_title": "Sla {name} op in je contacten", "vcf.page_body": "{store} heeft het team aangemeld voor oefengesprekken. Elk gesprek en elk scorekaart-bericht komt van dit nummer, dus sla het op en je weet altijd dat wij het zijn.",
        "vcf.page_body_generic": "Oefengesprekken en scorekaart-berichten komen van dit nummer. Sla het op en je weet altijd dat wij het zijn.", "vcf.save": "Contact opslaan", "vcf.hint": "iPhone: tik op het bestand en kies Nieuw contact. Android: open met Contacten.",
        "sum.none": "In {month} zijn er geen shops afgerond.",
        "sum.line": "{n} shop{s} afgerond in {month}{people}{avg}{need}",
        "dig.subject": "{store}: coachingoverzicht voor {label}", "dig.kicker": "I'M ON SOCIAL · COACHINGOVERZICHT VAN MAANDAG", "dig.morning": "Goedemorgen {name}. {line}",
        "dig.box.calls": "Gesprekken beoordeeld", "dig.box.avg": "Teamgemiddelde", "dig.box.crit": "Kritieke missers", "dig.box.unread": "Ongelezen coaching",
        "dig.none": "Vorige week zijn er geen gesprekken beoordeeld. Opgenomen gesprekken langer dan 30 seconden worden automatisch beoordeeld zodra er een scorekaart van toepassing is.",
        "dig.open": "Open Team Gespreksscores", "dig.hint": "Tik in de app op een medewerker om de gesprekken te horen en een beoordeling aan te passen. Medewerkers tikken \"Begrepen\" op hun coaching; dat telt als gelezen.",
        "dig.footer": "Je ontvangt dit omdat je {store} aanstuurt. Zet het uit onder Team Gespreksscores in de app.", "dig.coach_on": "COACH {name} HIEROP", "dig.hit": "{a} van {b} geraakt", "dig.critical": "KRITIEK",
        "dig.perfect": "Elk punt in elk beoordeeld gesprek geraakt. Zeg het ze.", "dig.first_week": "eerste beoordeelde week", "dig.vs": "{v} t.o.v. de week ervoor", "dig.unread": "{n} coaching ongelezen", "dig.read_all": "alle coaching gelezen",
        "dig.calls": "{n} gesprek", "dig.calls_p": "{n} gesprekken", "dig.best": "beste {v}%", "dig.crit_n": "{n} kritieke misser", "dig.crit_np": "{n} kritieke missers", "dig.no_crit": "geen kritieke missers",
    },
}

# British and Irish English: same pages, the words a UK or Irish dealer actually uses. Missing keys fall back to "en".
T["en-GB"] = {
    "prop.what.body": "I'm On Social will mystery shop {client} by phone every month: {per} calls, placed by our AI caller at random times during your opening hours. Every call is recorded, transcribed and graded against a phone skills scorecard and the scenario's success points, with written coaching for each person.",
    "prop.part.body": "Provide the names, mobile numbers and department of the people to shop, your opening hours, and a few real vehicles or services our caller can reference. You confirm you have the right to have your staff's business calls recorded and evaluated for training, and that you have told them calls may be recorded.",
    "prop.invest.body": "{price} per month, billed monthly by invoice (card or Bacs bank transfer) for an initial term of {term} months, then month to month. The first invoice is sent as soon as this proposal is signed and shops begin once it is paid.",
    "prop.agree.body": "By typing your name and signing below you agree to these terms on behalf of the business. This electronic signature is legally binding under the UK eIDAS Regulation and the Electronic Communications Act 2000.",
    "sms.intro": "Hi {name}, that practice call just now was from I'm On Social{store}.",
    "sms.intro_text": "Hi {name}, those texts just now were a practice shop from I'm On Social{store}.",
    "sms.intro_email": "Hi {name}, that email thread just now was a practice shop from I'm On Social{store}.",
}
T["en-IE"] = {
    **T["en-GB"],
    "prop.invest.body": "{price} per month, billed monthly by invoice (card or SEPA bank transfer) for an initial term of {term} months, then month to month. The first invoice is sent as soon as this proposal is signed and shops begin once it is paid.",
    "prop.agree.body": "By typing your name and signing below you agree to these terms on behalf of the business. This electronic signature is legally binding under the eIDAS Regulation (EU) 910/2014 and the Electronic Commerce Act 2000.",
}

MONTHS = {"nl": ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"]}
MONTHS_SHORT = {"nl": ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]}


def t(lang: Optional[str], key: str, **kw) -> str:
    lang = lang or "en"
    s = T.get(lang, {}).get(key) or T.get(lang[:2], {}).get(key) or T["en"].get(key) or key
    try:
        return s.format(**kw) if kw else s
    except (KeyError, IndexError):
        return s


def month_label(dt, lang: Optional[str], short: bool = False) -> str:
    """'September 2026' / 'september 2026' / 'sep' in the client's language."""
    if lang in MONTHS:
        return (MONTHS_SHORT if short else MONTHS)[lang][dt.month - 1] + ("" if short else f" {dt.year}")
    return dt.strftime("%b" if short else "%B %Y")
