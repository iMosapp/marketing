"""Call scorecards: manager-built QA checklists per department, graded by AI the moment a call transcript lands.
A scorecard = criteria (text, coaching hint, weight, critical). An evaluation = one graded call
(pass/fail per criterion with evidence, score %, summary, coaching, critical misses -> manager alerts)."""
import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId

from routers.database import get_db
from services.lead_flows import MANAGER_ROLES, user_store_id
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

COLL = "scorecards"
EVAL_COLL = "call_evaluations"
MIN_DURATION_S = 30
MODEL = ("openai", "gpt-5.2")
DEPARTMENTS = ["Internet Sales", "Sales Floor", "Service BDC", "Service Advisor", "Finance", "Parts", "Rental", "Body Shop"]

TEMPLATES = [
    {
        "key": "internet_sales", "name": "Internet Sales Call", "department": "Internet Sales",
        "description": "Every internet lead call: confirm the car, ask for the trade, set a firm appointment.",
        "criteria": [
            {"text": "Greeted the customer by name and introduced themselves and the dealership", "hint": "Open with your name, the store and why you are calling.", "weight": 1, "critical": False},
            {"text": "Confirmed the vehicle of interest and its availability", "hint": "Name the exact unit they asked about and confirm it is still here.", "weight": 1, "critical": False},
            {"text": "Asked discovery questions about needs and timeline", "hint": "Ask what they will use it for and when they want to be driving it.", "weight": 1, "critical": False},
            {"text": "Asked about a trade-in", "hint": "Always ask: 'Will you have a vehicle to trade?'", "weight": 2, "critical": True},
            {"text": "Asked for an appointment", "hint": "Ask for the visit every call. 'When can you come see it, today or tomorrow?'", "weight": 2, "critical": True},
            {"text": "Set a specific day and time for the appointment", "hint": "Offer two choices: 'Does 4:30 or 6:00 work better?'", "weight": 2, "critical": False},
            {"text": "Confirmed the customer's phone number or email", "hint": "Repeat the number back and confirm the best way to reach them.", "weight": 1, "critical": False},
            {"text": "Offered alternatives if the vehicle was not available", "hint": "Have two similar units ready before the call. Mark N/A when the unit was available.", "weight": 1, "critical": False},
            {"text": "Recapped next steps and thanked the customer", "hint": "Close with who does what next and a genuine thank you.", "weight": 1, "critical": False},
        ],
    },
    {
        "key": "service_bdc", "name": "Service BDC Call", "department": "Service BDC",
        "description": "Service appointment calls: identify the concern, book the first available slot, recap.",
        "criteria": [
            {"text": "Greeted the customer by name and introduced the service department", "hint": "Name, department, store. Warm and unhurried.", "weight": 1, "critical": False},
            {"text": "Confirmed the vehicle (year, make, model or mileage)", "hint": "Verify which vehicle before quoting anything.", "weight": 1, "critical": False},
            {"text": "Identified the customer's concern or service needed", "hint": "Ask what they are noticing and when it started.", "weight": 1, "critical": False},
            {"text": "Offered the first available appointment", "hint": "Lead with the soonest opening, then alternatives.", "weight": 2, "critical": True},
            {"text": "Set a specific day and time", "hint": "Two choices, then confirm.", "weight": 2, "critical": False},
            {"text": "Mentioned transportation options (shuttle, loaner or waiting area)", "hint": "Remove the 'how do I get home' objection before they raise it.", "weight": 1, "critical": False},
            {"text": "Confirmed the customer's phone number or email", "hint": "Repeat it back so the reminder text lands.", "weight": 1, "critical": False},
            {"text": "Recapped the appointment details", "hint": "Day, time, advisor, what to bring.", "weight": 1, "critical": False},
        ],
    },
    {
        "key": "phone_up", "name": "Sales Phone-Up", "department": "Sales Floor",
        "description": "Inbound sales calls: get the name and number, sell the appointment, not the car.",
        "criteria": [
            {"text": "Answered with their name and the dealership", "hint": "Professional open every time.", "weight": 1, "critical": False},
            {"text": "Got the customer's name", "hint": "Ask early and use it.", "weight": 1, "critical": False},
            {"text": "Got the customer's phone number", "hint": "'In case we get disconnected, what is the best number for you?'", "weight": 2, "critical": True},
            {"text": "Identified the vehicle of interest", "hint": "Which unit, and what drew them to it.", "weight": 1, "critical": False},
            {"text": "Asked about a trade-in", "hint": "Every call.", "weight": 1, "critical": False},
            {"text": "Asked for an appointment", "hint": "Sell the visit, not the price.", "weight": 2, "critical": True},
            {"text": "Set a specific day and time", "hint": "Offer two times.", "weight": 2, "critical": False},
            {"text": "Recapped and thanked the customer", "hint": "Confirm the plan and thank them for calling.", "weight": 1, "critical": False},
        ],
    },
    {
        "key": "parts_phone", "name": "Parts Counter Call", "department": "Parts",
        "description": "Inbound parts calls: pin down the exact vehicle, quote clearly, and turn the call into a sale or a pickup.",
        "criteria": [
            {"text": "Answered with their name and the parts department", "hint": "Name, department, store. Sound glad they called.", "weight": 1, "critical": False},
            {"text": "Got the customer's name", "hint": "Ask early and use it.", "weight": 1, "critical": False},
            {"text": "Confirmed the exact vehicle (year, make, model, trim or VIN)", "hint": "The right part starts with the right VIN. Ask for it or the year, model and trim.", "weight": 2, "critical": True},
            {"text": "Confirmed the part and checked availability", "hint": "Say what you are looking up and whether it is on the shelf or how fast it arrives.", "weight": 2, "critical": True},
            {"text": "Quoted the price clearly, including core, tax or shipping if relevant", "hint": "One clear number and what it includes. Never make them guess.", "weight": 1, "critical": False},
            {"text": "Explained the OEM advantage without knocking aftermarket", "hint": "Fit, warranty, and it is the part the car came with.", "weight": 1, "critical": False},
            {"text": "Asked for the sale or offered to hold or order the part", "hint": "'Want me to set it aside for you?' or 'I can have it here tomorrow, should I order it?'", "weight": 2, "critical": False},
            {"text": "Got the customer's phone number", "hint": "For the ready-for-pickup call or text.", "weight": 1, "critical": False},
            {"text": "Recapped part, price, timing and thanked the customer", "hint": "Repeat the part, the price and when it is ready.", "weight": 1, "critical": False},
        ],
    },
    {
        "key": "rental_phone", "name": "Rental Desk Call", "department": "Rental",
        "description": "Inbound rental calls: understand the need, offer the right vehicle, state the terms plainly, book it.",
        "criteria": [
            {"text": "Answered with their name and the rental department", "hint": "Name, department, store.", "weight": 1, "critical": False},
            {"text": "Got the customer's name", "hint": "Ask early and use it.", "weight": 1, "critical": False},
            {"text": "Asked when they need the vehicle and for how long", "hint": "Pickup date, return date, and how many people or how much cargo.", "weight": 2, "critical": True},
            {"text": "Asked the reason for the rental (insurance, service loaner, trip)", "hint": "Insurance and warranty rentals bill differently. Ask up front.", "weight": 1, "critical": False},
            {"text": "Offered a specific vehicle that fits the need", "hint": "Name a class or a unit, not 'we have lots of stuff'.", "weight": 2, "critical": True},
            {"text": "Stated the daily rate and what it includes", "hint": "Rate, mileage, fuel, insurance options, deposit.", "weight": 1, "critical": False},
            {"text": "Explained requirements (age, license, card, deposit)", "hint": "So there are no surprises at the counter.", "weight": 1, "critical": False},
            {"text": "Asked to reserve it and confirmed pickup time", "hint": "'Should I hold that for you at 9 tomorrow?'", "weight": 2, "critical": False},
            {"text": "Got the customer's phone number and recapped", "hint": "Number for the confirmation, then recap vehicle, time, rate.", "weight": 1, "critical": False},
        ],
    },
    {
        "key": "collision_phone", "name": "Body Shop Call", "department": "Body Shop",
        "description": "Inbound collision calls: calm the customer, learn the damage and the claim, book the estimate, never quote blind.",
        "criteria": [
            {"text": "Answered with their name and the body shop", "hint": "Name, department, store. Calm and glad they called.", "weight": 1, "critical": False},
            {"text": "Got the customer's name", "hint": "Ask early and use it.", "weight": 1, "critical": False},
            {"text": "Showed empathy about the accident", "hint": "'I'm glad you're okay' before any process talk.", "weight": 1, "critical": False},
            {"text": "Confirmed the vehicle, the damage and whether it is drivable", "hint": "Year, make, model, where the damage is, does it drive straight, any lights on.", "weight": 2, "critical": True},
            {"text": "Asked whether a claim is open and which insurance company", "hint": "Their carrier or the other driver's. Claim number if they have it.", "weight": 2, "critical": True},
            {"text": "Explained the estimate process instead of quoting a price blind", "hint": "Photos are a start, the real number comes from a teardown. Say how long the estimate takes.", "weight": 2, "critical": False},
            {"text": "Mentioned rental or transportation options", "hint": "Rental coordination, shuttle or a ride, before they ask.", "weight": 1, "critical": False},
            {"text": "Offered a specific estimate or drop-off time with two options", "hint": "'Can you swing by at 10 tomorrow or 3 this afternoon?'", "weight": 2, "critical": True},
            {"text": "Got the customer's phone number and recapped", "hint": "Number for updates, then recap time, what to bring (claim number, insurance card).", "weight": 1, "critical": False},
        ],
    },
    {
        "key": "service_followup", "name": "Service Follow-Up Call", "department": "Service Advisor",
        "description": "Outbound service calls (recall letter, declined repair, overdue maintenance): open with name and reason, tie it to their vehicle, book it.",
        "criteria": [
            {"text": "Opened with their name, the store and the reason for calling", "hint": "'Hi Angela, it's Sam at LHM Service, calling about the recall notice on your Grand Cherokee.' No mystery about who or why.", "weight": 1, "critical": False},
            {"text": "Confirmed they had a minute to talk", "hint": "You called them. Ask, and offer a callback time if not.", "weight": 1, "critical": False},
            {"text": "Referenced the specific vehicle and the specific item (recall, declined work, overdue service)", "hint": "Year, model, mileage or the repair line. Show you looked before you dialed.", "weight": 2, "critical": True},
            {"text": "Explained what it is and why it matters in plain words", "hint": "Safety, cost of waiting, or that it is no charge. One or two sentences, no jargon.", "weight": 2, "critical": False},
            {"text": "Answered their questions honestly (cost, time, warranty)", "hint": "A range and what changes it beats a dodge.", "weight": 1, "critical": False},
            {"text": "Offered two specific appointment times", "hint": "'Thursday at 8 or Saturday at 10?'", "weight": 2, "critical": True},
            {"text": "Mentioned transportation options (shuttle, loaner or waiting area)", "hint": "Remove the 'how do I get to work' objection before they raise it.", "weight": 1, "critical": False},
            {"text": "Confirmed the best number or email for the reminder", "hint": "Repeat it back.", "weight": 1, "critical": False},
            {"text": "Recapped day, time and what happens next, and thanked them", "hint": "Close with the plan and a genuine thank you for their time.", "weight": 1, "critical": False},
        ],
    },
    {
        "key": "parts_followup", "name": "Parts Follow-Up Call", "department": "Parts",
        "description": "Outbound parts calls (part arrived, quote follow-up, backorder update): identify, reference the exact part, give clear status, close the pickup or install.",
        "criteria": [
            {"text": "Opened with their name, the parts department and the reason for calling", "hint": "'Hi Ray, it's Sam in Parts at LHM, your brake pads came in.'", "weight": 1, "critical": False},
            {"text": "Referenced the exact part and vehicle", "hint": "Part name, the vehicle it fits, the order or quote they know about.", "weight": 2, "critical": True},
            {"text": "Gave clear status (in stock now, arrives when, backorder and the real date)", "hint": "A date beats 'soon'. If it slipped, say so and why.", "weight": 2, "critical": True},
            {"text": "Confirmed the price and what it includes (core, tax, install if quoted)", "hint": "One clear number so there is no surprise at the counter.", "weight": 1, "critical": False},
            {"text": "Offered installation or a related item where it fits", "hint": "'Want service to put them on while you wait?' Once, not pushy.", "weight": 1, "critical": False},
            {"text": "Asked for a pickup or install time and stated counter hours", "hint": "'We're open till 6; morning or afternoon work better?'", "weight": 2, "critical": False},
            {"text": "Confirmed how long the part is held and the best number for updates", "hint": "Hold period and a callback number.", "weight": 1, "critical": False},
            {"text": "Recapped part, price, timing and thanked them", "hint": "Repeat the plan and thank them for ordering with you.", "weight": 1, "critical": False},
        ],
    },
    {
        "key": "rental_followup", "name": "Rental Follow-Up Call", "department": "Rental",
        "description": "Outbound rental calls (reservation confirmation, insurance rental setup, return reminder): confirm the details, remove surprises, lock the pickup.",
        "criteria": [
            {"text": "Opened with their name, the rental department and the reason for calling", "hint": "'Hi Monica, it's Sam at LHM Rental, confirming your car for tomorrow.'", "weight": 1, "critical": False},
            {"text": "Confirmed the reservation details (vehicle or class, pickup date and time, return date)", "hint": "Read them back and fix anything that changed.", "weight": 2, "critical": True},
            {"text": "Confirmed the billing arrangement (insurance direct bill and daily allowance, or the retail rate and what it includes)", "hint": "Who pays, how much per day, what happens above the allowance.", "weight": 2, "critical": True},
            {"text": "Reminded them what to bring (license, credit card for the deposit, claim number)", "hint": "So nobody is turned away at the counter.", "weight": 1, "critical": False},
            {"text": "Asked about needs that change the vehicle (seats, car seat, hitch, mileage)", "hint": "Catch it now, not at pickup.", "weight": 1, "critical": False},
            {"text": "Offered a relevant option once (upgrade, second driver, insurance waiver) without pushing", "hint": "One offer, then move on.", "weight": 1, "critical": False},
            {"text": "Confirmed the pickup time and the best number for a text when the car is ready", "hint": "Time plus number, repeated back.", "weight": 2, "critical": False},
            {"text": "Recapped and thanked them", "hint": "Vehicle, time, what to bring, thank you.", "weight": 1, "critical": False},
        ],
    },
    {
        "key": "collision_followup", "name": "Body Shop Follow-Up Call", "department": "Body Shop",
        "description": "Outbound collision calls (estimate follow-up, repair status update, supplement approval): identify, empathize, give a straight status and a date, coordinate insurance and rental, set the next step.",
        "criteria": [
            {"text": "Opened with their name, the body shop and the reason for calling", "hint": "'Hi Nicole, it's Sam at LHM Collision with an update on your Grand Cherokee.'", "weight": 1, "critical": False},
            {"text": "Referenced their specific vehicle and repair (damage, claim, estimate they saw)", "hint": "Show you have the file open.", "weight": 2, "critical": True},
            {"text": "Gave a clear, honest status and a realistic completion or next-step date", "hint": "A date and why. If it slipped, say what happened (parts, supplement, insurer).", "weight": 2, "critical": True},
            {"text": "Explained the insurance side (supplement, approval, deductible) in plain words", "hint": "Who is waiting on whom and what the customer has to do, if anything.", "weight": 2, "critical": False},
            {"text": "Addressed the rental or transportation situation", "hint": "Days left on the rental, extension handled, or a ride arranged.", "weight": 1, "critical": False},
            {"text": "Answered their questions directly (parts used, warranty, cost) without guessing", "hint": "Straight answers; 'let me check and call you by 3' beats a guess.", "weight": 1, "critical": False},
            {"text": "Set the next step with a specific time (drop-off, pickup, next update call)", "hint": "'I'll call you Thursday by noon' or 'pickup Friday after 2'.", "weight": 2, "critical": False},
            {"text": "Confirmed the best number for updates and thanked them", "hint": "Number repeated back, thank you for their patience.", "weight": 1, "critical": False},
        ],
    },
]


def _now():
    return datetime.now(timezone.utc)



def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


def _oid(v):
    return ObjectId(str(v)) if ObjectId.is_valid(str(v or "")) else None


def _first(u: Optional[dict]) -> str:
    return ((u or {}).get("first_name") or ((u or {}).get("name") or "Rep").split(" ")[0])


# ---------------------------------------------------------------- scorecards
def normalize_criteria(raw: list) -> list:
    out = []
    for c in raw or []:
        text = (c.get("text") or "").strip()
        if not text:
            continue
        try:
            weight = max(1, min(5, int(c.get("weight") or 1)))
        except (TypeError, ValueError):
            weight = 1
        out.append({"id": c.get("id") or uuid.uuid4().hex[:8], "text": text[:200], "hint": (c.get("hint") or "").strip()[:300],
                    "weight": weight, "critical": bool(c.get("critical"))})
    return out[:25]


def serialize(card: dict, extra: Optional[dict] = None) -> dict:
    a = card.get("applies_to") or {}
    out = {
        "id": str(card["_id"]), "name": card.get("name") or "Scorecard", "department": card.get("department") or "",
        "description": card.get("description") or "", "criteria": card.get("criteria") or [],
        "applies_to": {"user_ids": a.get("user_ids") or [], "inbox_ids": a.get("inbox_ids") or [], "source_ids": a.get("source_ids") or []},
        "is_default": bool(card.get("is_default")), "active": card.get("active", True) is not False,
        "alert_on_critical": card.get("alert_on_critical", True) is not False,
        "alert_below_pct": card.get("alert_below_pct"), "notify_rep": card.get("notify_rep", True) is not False,
        "store_id": card.get("store_id"), "template_key": card.get("template_key"),
        "created_at": _iso(card.get("created_at")), "updated_at": _iso(card.get("updated_at")),
    }
    out["critical_count"] = sum(1 for c in out["criteria"] if c.get("critical"))
    if extra:
        out.update(extra)
    return out


def templates_for(industry_key: Optional[str]) -> list:
    """Starter scorecards for a store: the hand-built automotive set, or one per department from the store's industry pack."""
    from services import industries as ind
    if (industry_key or ind.DEFAULT_INDUSTRY) == ind.DEFAULT_INDUSTRY:
        return TEMPLATES
    out = []
    for d in ind.departments(industry_key):
        card = d.get("scorecard")
        if not card:
            continue
        brief = d["brief"].split(";")[0].strip()
        out.append({"key": f"pack:{d['key']}", "name": card["name"], "department": d["label"], "description": (brief[0].upper() + brief[1:])[:180] + ".", "criteria": card["criteria"]})
    return out


def departments_for(industry_key: Optional[str]) -> list:
    from services import industries as ind
    if (industry_key or ind.DEFAULT_INDUSTRY) == ind.DEFAULT_INDUSTRY:
        return DEPARTMENTS
    return [d["label"] for d in ind.departments(industry_key)]


# Dutch wording for the automotive templates (same order and count as the English criteria; ids stay the same so grading history lines up)
TEMPLATE_TRANSLATIONS = {
    "nl": {
        "phone_up": {"name": "Inkomend verkoopgesprek", "department": "Verkoop", "description": "Inkomende verkoopgesprekken: naam en nummer vragen, de afspraak verkopen, niet de auto.",
                     "criteria": [("Nam op met eigen naam en de naam van het autobedrijf", "Elke keer een professionele opening."), ("Vroeg de naam van de klant", "Vraag het vroeg en gebruik de naam."),
                                  ("Vroeg het telefoonnummer van de klant", "'Voor het geval de verbinding wegvalt, wat is het beste nummer?'"), ("Achterhaalde welke auto de klant bedoelt", "Welke auto, en wat sprak hem of haar aan."),
                                  ("Vroeg naar een inruilauto", "Elk gesprek."), ("Vroeg om een afspraak", "Verkoop het bezoek, niet de prijs."), ("Legde een concrete dag en tijd vast", "Bied twee tijden aan."),
                                  ("Vatte samen en bedankte de klant", "Bevestig het plan en bedank voor het bellen.")]},
        "internet_sales": {"name": "Internetlead-gesprek", "department": "Verkoop", "description": "Elk internetlead-gesprek: bevestig de auto, vraag naar de inruil, leg een vaste afspraak vast.",
                           "criteria": [("Begroette de klant met naam en stelde zichzelf en het autobedrijf voor", "Open met je naam, het bedrijf en waarom je belt."), ("Bevestigde de auto en of die nog beschikbaar is", "Noem precies de auto waar ze naar vroegen en bevestig dat hij er nog staat."),
                                        ("Stelde vragen over wensen en tijdlijn", "Vraag waarvoor ze de auto gebruiken en wanneer ze willen rijden."), ("Vroeg naar een inruilauto", "Altijd vragen: 'Heb je een auto om in te ruilen?'"),
                                        ("Vroeg om een afspraak", "Vraag elk gesprek om het bezoek. 'Wanneer kom je kijken, vandaag of morgen?'"), ("Legde een concrete dag en tijd vast", "Bied twee keuzes: 'Past half vijf of zes uur beter?'"),
                                        ("Bevestigde telefoonnummer of e-mail van de klant", "Herhaal het nummer en bevestig hoe je ze het beste bereikt."), ("Bood alternatieven als de auto niet beschikbaar was", "Heb twee vergelijkbare auto's klaar. Markeer n.v.t. als de auto beschikbaar was."),
                                        ("Vatte de vervolgstappen samen en bedankte de klant", "Sluit af met wie wat doet en een oprecht bedankje.")]},
        "service_bdc": {"name": "Werkplaatsafspraak-gesprek", "department": "Werkplaats", "description": "Servicegesprekken: achterhaal de klacht, plan de eerste beschikbare plek, vat samen.",
                        "criteria": [("Begroette de klant met naam en noemde de werkplaats", "Naam, afdeling, bedrijf. Warm en zonder haast."), ("Bevestigde de auto (bouwjaar, merk, model of kilometerstand)", "Controleer om welke auto het gaat voordat je iets noemt."),
                                     ("Achterhaalde de klacht of de gewenste service", "Vraag wat ze merken en sinds wanneer."), ("Bood de eerste beschikbare afspraak aan", "Begin met de eerste vrije plek, dan alternatieven."),
                                     ("Legde een concrete dag en tijd vast", "Twee keuzes, dan bevestigen."), ("Noemde vervoersopties (haal- en brengservice, leenauto of wachtruimte)", "Neem het 'hoe kom ik thuis' bezwaar weg voordat het komt."),
                                     ("Bevestigde telefoonnummer of e-mail van de klant", "Herhaal het zodat de herinnering aankomt."), ("Vatte de afspraak samen", "Dag, tijd, adviseur, wat mee te nemen.")]},
        "parts_phone": {"name": "Onderdelenbalie-gesprek", "department": "Onderdelen", "description": "Inkomende onderdelengesprekken: de exacte auto vaststellen, duidelijk een prijs noemen, en het gesprek omzetten in een verkoop of afhaling.",
                        "criteria": [("Nam op met eigen naam en de onderdelenafdeling", "Naam, afdeling, bedrijf. Klink blij dat ze bellen."), ("Vroeg de naam van de klant", "Vraag het vroeg en gebruik de naam."),
                                     ("Bevestigde de exacte auto (bouwjaar, merk, model, uitvoering of chassisnummer)", "Het juiste onderdeel begint bij het juiste chassisnummer. Vraag ernaar, of naar bouwjaar, model en uitvoering."),
                                     ("Bevestigde het onderdeel en controleerde de voorraad", "Zeg wat je opzoekt en of het op de plank ligt of hoe snel het er is."), ("Noemde de prijs duidelijk, inclusief statiegeld, btw of verzendkosten als dat speelt", "Eén duidelijk bedrag en wat erbij zit. Laat ze nooit raden."),
                                     ("Legde het voordeel van origineel uit zonder af te geven op imitatie", "Passing, garantie, en het is het onderdeel waarmee de auto gebouwd is."), ("Vroeg om de verkoop of bood aan het onderdeel te reserveren of te bestellen", "'Zal ik hem voor je apart leggen?' of 'Ik kan hem morgen hier hebben, zal ik bestellen?'"),
                                     ("Vroeg het telefoonnummer van de klant", "Voor het belletje of berichtje dat het klaarligt."), ("Vatte onderdeel, prijs en timing samen en bedankte de klant", "Herhaal het onderdeel, de prijs en wanneer het klaar is.")]},
        "rental_phone": {"name": "Verhuurbalie-gesprek", "department": "Verhuur", "description": "Inkomende verhuurgesprekken: de behoefte begrijpen, de juiste auto aanbieden, de voorwaarden helder noemen, reserveren.",
                         "criteria": [("Nam op met eigen naam en de verhuurafdeling", "Naam, afdeling, bedrijf."), ("Vroeg de naam van de klant", "Vraag het vroeg en gebruik de naam."),
                                      ("Vroeg wanneer en hoe lang de klant de auto nodig heeft", "Ophaaldatum, inleverdatum en hoeveel personen of bagage."), ("Vroeg de reden van de huur (verzekering, leenauto bij onderhoud, vakantie)", "Verzekerings- en garantiehuur worden anders gefactureerd. Vraag het vooraf."),
                                      ("Bood een concrete auto aan die past", "Noem een klasse of een auto, niet 'we hebben van alles'."), ("Noemde het dagtarief en wat erbij zit", "Tarief, kilometers, brandstof, verzekeringsopties, borg."),
                                      ("Legde de voorwaarden uit (leeftijd, rijbewijs, kaart, borg)", "Zodat er geen verrassingen zijn aan de balie."), ("Vroeg om te reserveren en bevestigde de ophaaltijd", "'Zal ik hem morgen om negen uur voor je vasthouden?'"),
                                      ("Vroeg het telefoonnummer van de klant en vatte samen", "Nummer voor de bevestiging, dan auto, tijd en tarief herhalen.")]},
        "collision_phone": {"name": "Schadeherstel-gesprek", "department": "Schadeherstel", "description": "Inkomende schadegesprekken: de klant geruststellen, de schade en de claim achterhalen, de taxatie inplannen, nooit blind een prijs noemen.",
                            "criteria": [("Nam op met eigen naam en de schadeafdeling", "Naam, afdeling, bedrijf. Rustig en blij dat ze bellen."), ("Vroeg de naam van de klant", "Vraag het vroeg en gebruik de naam."),
                                         ("Toonde begrip voor het ongeluk", "'Fijn dat je in orde bent' voordat je over de procedure praat."), ("Bevestigde de auto, de schade en of er nog mee gereden kan worden", "Bouwjaar, merk, model, waar de schade zit, rijdt hij recht, branden er lampjes."),
                                         ("Vroeg of er een schadeclaim loopt en bij welke verzekeraar", "Hun verzekeraar of die van de tegenpartij. Schadenummer als ze het hebben."), ("Legde de taxatieprocedure uit in plaats van blind een prijs te noemen", "Foto's zijn een begin, het echte bedrag komt na demontage. Zeg hoe lang de taxatie duurt."),
                                         ("Noemde vervangend vervoer of een leenauto", "Huurauto regelen, haal- en brengservice of een lift, voordat ze het vragen."), ("Bood een concrete taxatie- of inlevertijd aan met twee opties", "'Kun je morgen om tien uur langskomen, of vanmiddag om drie uur?'"),
                                         ("Vroeg het telefoonnummer van de klant en vatte samen", "Nummer voor updates, dan tijd herhalen en wat mee te nemen (schadenummer, verzekeringspas).")]},
        "service_followup": {"name": "Werkplaats-nabelgesprek", "department": "Werkplaats", "description": "Uitgaande servicegesprekken (terugroepactie, afgewezen reparatie, achterstallig onderhoud): open met naam en reden, koppel het aan hun auto, plan het in.",
                             "criteria": [("Opende met eigen naam, het bedrijf en de reden van het gesprek", "'Hoi Angela, met Sam van de werkplaats van LHM, ik bel over de terugroepactie op je Grand Cherokee.' Geen raadsel wie of waarom."),
                                          ("Vroeg of het gelegen kwam", "Jij belt hen. Vraag het, en bied een terugbelmoment aan als het niet uitkomt."),
                                          ("Verwees naar de specifieke auto en het specifieke punt (terugroepactie, afgewezen werk, achterstallig onderhoud)", "Bouwjaar, model, kilometerstand of de reparatieregel. Laat zien dat je gekeken hebt voordat je belde."),
                                          ("Legde in gewone woorden uit wat het is en waarom het belangrijk is", "Veiligheid, kosten van wachten, of dat het kosteloos is. Een of twee zinnen, geen jargon."),
                                          ("Beantwoordde vragen eerlijk (kosten, tijd, garantie)", "Een prijsindicatie en wat die verandert is beter dan ontwijken."),
                                          ("Bood twee concrete afspraaktijden aan", "'Donderdag om acht uur of zaterdag om tien uur?'"),
                                          ("Noemde vervoersopties (haal- en brengservice, leenauto of wachtruimte)", "Neem het 'hoe kom ik op mijn werk'-bezwaar weg voordat ze het noemen."),
                                          ("Bevestigde het beste nummer of e-mailadres voor de herinnering", "Herhaal het."),
                                          ("Vatte dag, tijd en vervolgstappen samen en bedankte de klant", "Sluit af met het plan en een oprecht dankjewel voor hun tijd.")]},
        "parts_followup": {"name": "Onderdelen-nabelgesprek", "department": "Onderdelen", "description": "Uitgaande onderdelengesprekken (onderdeel binnen, offerte-opvolging, nalevering): identificeer, noem het exacte onderdeel, geef heldere status, sluit de afhaling of montage.",
                           "criteria": [("Opende met eigen naam, de onderdelenafdeling en de reden van het gesprek", "'Hoi Ray, met Sam van Onderdelen bij LHM, je remblokken zijn binnen.'"),
                                        ("Verwees naar het exacte onderdeel en de auto", "Onderdeelnaam, de auto waar het op past, de bestelling of offerte die ze kennen."),
                                        ("Gaf heldere status (nu op voorraad, komt wanneer, nalevering met de echte datum)", "Een datum is beter dan 'binnenkort'. Als het uitloopt, zeg het en waarom."),
                                        ("Bevestigde de prijs en wat erbij zit (statiegeld, btw, montage als die geoffreerd is)", "Een helder bedrag zodat er aan de balie geen verrassing is."),
                                        ("Bood montage of een passend extra onderdeel aan waar het past", "'Zal de werkplaats ze meteen monteren terwijl je wacht?' Een keer, niet opdringerig."),
                                        ("Vroeg om een afhaal- of montagetijd en noemde de openingstijden", "'We zijn open tot zes; komt de ochtend of de middag beter uit?'"),
                                        ("Bevestigde hoe lang het onderdeel bewaard blijft en het beste nummer voor updates", "Bewaartermijn en een terugbelnummer."),
                                        ("Vatte onderdeel, prijs en timing samen en bedankte de klant", "Herhaal het plan en bedank ze dat ze bij jullie bestellen.")]},
        "rental_followup": {"name": "Verhuur-nabelgesprek", "department": "Verhuur", "description": "Uitgaande verhuurgesprekken (reserveringsbevestiging, verzekeringshuur regelen, herinnering inleveren): bevestig de details, voorkom verrassingen, leg het ophaalmoment vast.",
                            "criteria": [("Opende met eigen naam, de verhuurafdeling en de reden van het gesprek", "'Hoi Monica, met Sam van LHM Verhuur, ik bevestig je auto voor morgen.'"),
                                         ("Bevestigde de reserveringsgegevens (auto of klasse, ophaaldatum en -tijd, inleverdatum)", "Lees ze voor en corrigeer wat veranderd is."),
                                         ("Bevestigde de betaalafspraak (rechtstreeks via de verzekeraar met daglimiet, of het tarief en wat erbij zit)", "Wie betaalt, hoeveel per dag, wat er gebeurt boven de limiet."),
                                         ("Herinnerde aan wat mee te nemen (rijbewijs, creditcard voor de borg, schadenummer)", "Zodat niemand aan de balie wordt weggestuurd."),
                                         ("Vroeg naar behoeften die de auto veranderen (zitplaatsen, kinderzitje, trekhaak, kilometers)", "Vang het nu op, niet bij het ophalen."),
                                         ("Bood een keer een passende optie aan (upgrade, tweede bestuurder, afkoop eigen risico) zonder te pushen", "Een aanbod, dan verder."),
                                         ("Bevestigde de ophaaltijd en het beste nummer voor een berichtje als de auto klaarstaat", "Tijd plus nummer, herhaald."),
                                         ("Vatte samen en bedankte de klant", "Auto, tijd, wat mee te nemen, dankjewel.")]},
        "collision_followup": {"name": "Schadeherstel-nabelgesprek", "department": "Schadeherstel", "description": "Uitgaande schadegesprekken (taxatie-opvolging, statusupdate, goedkeuring meerwerk): identificeer, toon begrip, geef eerlijke status en een datum, stem verzekering en huurauto af, leg de volgende stap vast.",
                               "criteria": [("Opende met eigen naam, de schadeafdeling en de reden van het gesprek", "'Hoi Nicole, met Sam van LHM Schadeherstel, ik heb een update over je Grand Cherokee.'"),
                                            ("Verwees naar hun specifieke auto en reparatie (schade, claim, taxatie die ze zagen)", "Laat merken dat je het dossier open hebt."),
                                            ("Gaf een heldere, eerlijke status en een realistische datum voor oplevering of volgende stap", "Een datum en het waarom. Als het uitloopt, zeg wat er gebeurde (onderdelen, meerwerk, verzekeraar)."),
                                            ("Legde de verzekeringskant (meerwerk, goedkeuring, eigen risico) in gewone woorden uit", "Wie wacht op wie en wat de klant zelf moet doen, als er iets is."),
                                            ("Ging in op de huurauto of het vervoer", "Resterende huurdagen, verlenging geregeld, of een lift afgesproken."),
                                            ("Beantwoordde vragen direct (gebruikte onderdelen, garantie, kosten) zonder te gokken", "Rechte antwoorden; 'ik check het en bel je voor drie uur' is beter dan gokken."),
                                            ("Legde de volgende stap vast met een concreet moment (inleveren, ophalen, volgend belmoment)", "'Ik bel je donderdag voor twaalven' of 'ophalen vrijdag na twee uur'."),
                                            ("Bevestigde het beste nummer voor updates en bedankte de klant", "Nummer herhaald, dank voor hun geduld.")]},
    },
}


def template_body(key: str, language: Optional[str] = None) -> Optional[dict]:
    from services import industries as ind
    tpl = next((t for t in TEMPLATES if t["key"] == key), None)
    if not tpl and key.startswith("pack:"):
        tpl = next((t for t in templates_for(ind.industry_of_dept(key[5:])) if t["key"] == key), None)
    if not tpl:
        return None
    body = {k: v for k, v in tpl.items() if k != "key"}
    body["criteria"] = normalize_criteria(tpl["criteria"])
    body["template_key"] = key
    tr = TEMPLATE_TRANSLATIONS.get(language or "en", {}).get(key)
    if tr and len(tr["criteria"]) == len(body["criteria"]):
        body.update({"name": tr["name"], "department": tr["department"], "description": tr["description"], "language": language})
        body["criteria"] = [{**c, "text": t, "hint": h} for c, (t, h) in zip(body["criteria"], tr["criteria"])]
    return body


async def scope_store_ids(user: dict) -> Optional[list]:
    """Stores whose scorecards / evaluations this manager may see. None = everything (super admin)."""
    if user.get("role") == "super_admin":
        return None
    from routers.rbac import get_scoped_store_ids
    ids = [str(s) for s in await get_scoped_store_ids(user)]
    sid = user_store_id(user)
    if sid and sid not in ids:
        ids.append(sid)
    return ids


async def card_scope_filter(user: dict) -> dict:
    ids = await scope_store_ids(user)
    if ids is None:
        return {}
    ors = [{"store_id": {"$in": ids}}] if ids else []
    ors.append({"owner_user_id": str(user["_id"])})
    return {"$or": ors}


async def eval_scope_filter(user: dict) -> dict:
    """Reps: own calls only. Managers: every call in their store(s)."""
    if user.get("role") not in MANAGER_ROLES:
        return {"user_id": str(user["_id"])}
    ids = await scope_store_ids(user)
    if ids is None:
        return {"is_mystery_shop": {"$ne": True}}
    return {"$or": [{"store_id": {"$in": ids}}, {"user_id": str(user["_id"])}]}


async def store_cards(db, store_id: Optional[str]) -> list:
    q: dict = {"active": {"$ne": False}}
    if store_id:
        q["store_id"] = store_id
    else:
        q["store_id"] = None
    return await db[COLL].find(q).sort("created_at", 1).to_list(50)


async def pick_scorecard(db, rep: dict, conv: Optional[dict]) -> Optional[dict]:
    """Which card grades this call: inbox match > rep match > lead source match > store default."""
    cards = await store_cards(db, user_store_id(rep))
    if not cards:
        return None
    rep_id = str(rep["_id"])
    inbox_id = str((conv or {}).get("inbox_id") or "")
    source_id = str((conv or {}).get("lead_source_id") or (conv or {}).get("source_id") or "")
    for key, val in (("inbox_ids", inbox_id), ("user_ids", rep_id), ("source_ids", source_id)):
        if not val:
            continue
        for c in cards:
            if val in ((c.get("applies_to") or {}).get(key) or []):
                return c
    return next((c for c in cards if c.get("is_default")), None)


async def ensure_single_default(db, store_id: Optional[str], keep_id: ObjectId):
    await db[COLL].update_many({"store_id": store_id, "_id": {"$ne": keep_id}, "is_default": True}, {"$set": {"is_default": False}})


# ---------------------------------------------------------------- grading
def miss_labels(ev: dict) -> list:
    ids = set(ev.get("critical_misses") or [])
    return [r.get("text") or r["criterion_id"] for r in ev.get("results") or [] if r.get("criterion_id") in ids]


def compute_score(results: list, criteria: list) -> tuple:
    weights = {c["id"]: int(c.get("weight") or 1) for c in criteria}
    crit = {c["id"]: bool(c.get("critical")) for c in criteria}
    total = earned = 0
    misses = []
    for r in results:
        p = r.get("passed")
        if p is None:
            continue
        w = weights.get(r["criterion_id"], 1)
        total += w
        if p:
            earned += w
        elif crit.get(r["criterion_id"]):
            misses.append(r["criterion_id"])
    pct = int(round(100 * earned / total)) if total else None
    return pct, misses


def _transcript_text(log: dict, rep_name: str) -> str:
    segs = log.get("transcript_segments") or []
    if segs:
        lines = []
        for s in segs:
            who = f"REP ({rep_name})" if s.get("role") == "rep" else "CUSTOMER"
            t = s.get("start")
            stamp = f"[{int(t // 60)}:{int(t % 60):02d}] " if isinstance(t, (int, float)) else ""
            lines.append(f"{stamp}{who}: {s.get('text', '')}")
        return "\n".join(lines)
    return (log.get("transcript") or "").strip()


GRADER_LANGUAGE = {"nl": ("- LANGUAGE: the call is in Dutch. Write summary, wins and coaching in natural Dutch (Nederlands), addressing the rep as 'je'. "
                          "Keep the criterion ids exactly as given and the JSON keys in English.\n"),
                   "en-GB": ("- LANGUAGE: the call is at a UK dealership. Write summary, wins and coaching in British English (spelling and trade words: part exchange, MOT, reg, bonnet, boot, tyres, £, miles). "
                             "Keep the criterion ids exactly as given and the JSON keys in English.\n"),
                   "en-IE": ("- LANGUAGE: the call is at an Irish dealership. Write summary, wins and coaching in Irish English (part exchange, NCT, reg, bonnet, boot, tyres, €, kilometres). "
                             "Keep the criterion ids exactly as given and the JSON keys in English.\n")}


def grader_language_rule(language: Optional[str]) -> str:
    lang = language or "en"
    return GRADER_LANGUAGE.get(lang) or GRADER_LANGUAGE.get(lang[:2]) or ""


def _grader_prompt(card: dict, rep_name: str, contact_name: str, direction: str, duration_s: int, industry: Optional[str] = None, language: Optional[str] = None, channel: str = "call") -> str:
    from services import industries as ind
    coach = "dealership call-quality coach" if (industry or ind.DEFAULT_INDUSTRY) == "automotive" else f"{ind.get(industry)['label'].lower()} call-quality coach"
    crit_lines = "\n".join(
        f'- id "{c["id"]}": {c["text"]}' + (" (CRITICAL)" if c.get("critical") else "") + (f' | coaching hint: {c["hint"]}' if c.get("hint") else "")
        for c in card.get("criteria") or []
    )
    text = channel == "text"
    email = channel == "email"
    medium = (f"a text message (SMS) conversation ({max(1, duration_s // 60)} min from first text to last)" if text
              else f"an email thread ({max(1, duration_s // 3600)} h from the first email to the last)" if email
              else f"a recorded {direction} phone call ({duration_s}s)")
    who_called = ("" if text or email else
                  ("- CALL TYPE: OUTBOUND. The rep placed this call to a customer who had left a lead or has an open item (recall, part, reservation, estimate). The customer answers with a plain hello and the rep must open with their name, the store and the reason for calling, then drive the conversation. "
                   "Grade 'answered with their name and department' style criteria as 'opened with name, store and reason'.\n"
                   if direction == "outbound" else
                   "- CALL TYPE: INBOUND. The customer called the store; the rep answered. The rep is expected to answer with the store and their name, get the caller's name and number early, and steer toward a visit.\n"))
    return (
        f"You are a {coach} grading {medium} between the rep {rep_name} "
        f"and the customer {contact_name} using the '{card.get('name')}' scorecard ({card.get('department') or 'Sales'} department).\n\n"
        "CRITERIA to grade (each must appear in your results):\n" + crit_lines + "\n\n"
        "RULES:\n" + who_called +
        "- passed = true only when the transcript clearly shows the REP did it. Unclear or missing = false.\n"
        "- passed = null ONLY when the criterion genuinely did not apply on this call (e.g. 'offered alternatives if unavailable' when the unit was available).\n"
        "- evidence = a short verbatim quote (max 140 chars) from the transcript that proves your call, or \"\" when nothing supports it.\n"
        "- confidence = 0.0 to 1.0.\n"
        "- summary = 2 or 3 plain sentences: what the customer wanted, what the rep did, how it ended.\n"
        "- wins = 1 or 2 specific things the rep did well.\n"
        "- coaching = 2 or 3 specific, kind, actionable tips tied to what was missed, each one sentence, written to the rep as 'you'.\n"
        "- Never use em dashes or en dashes anywhere. Use commas or periods.\n"
        + ("- This was a TEXT thread: the customer texted first like a real text lead. '[replied after N min]' notes show how long the rep took; the reply-speed criteria are measured by the system, so grade the other criteria on what the rep wrote. "
           "Phone-only behaviours do not apply to texts: pass them when the rep did the text equivalent, and use null only when a criterion truly cannot apply to a text conversation.\n"
           if text else
           "- This was an EMAIL thread: the customer emailed first like a real internet lead. '[replied after N]' notes show how long the rep took; the reply-speed criteria are measured by the system, so grade the other criteria on what the rep wrote. "
           "Judge the emails the way a buyer would: did the rep actually answer the question, personalise beyond a template, give a clear next step and make it easy to reply. "
           "Phone-only behaviours do not apply to email: pass them when the rep did the email equivalent, and use null only when a criterion truly cannot apply to an email conversation.\n"
           if email else "- If the recording is a voicemail, hold music or the customer never speaks, set call_type to \"no_conversation\" and grade what you can.\n")
        + grader_language_rule(language) + "\n"
        "Respond with ONLY valid JSON in exactly this shape:\n"
        '{"summary": "...", "wins": ["..."], "coaching": ["..."], "customer_sentiment": "positive|neutral|negative", '
        '"call_type": "conversation|no_conversation", "results": [{"id": "criterion id", "passed": true, "evidence": "...", "confidence": 0.9}]}'
    )


def _parse_json(raw: str) -> dict:
    """Graders sometimes wrap the JSON in prose or escape the quotes around a value; try the lenient forms before giving up."""
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned)
    if cleaned.startswith("json"):
        cleaned = cleaned[4:].strip()
    m = re.search(r"\{.*\}", cleaned, re.S)
    if m:
        cleaned = m.group(0)
    lenient = re.sub(r'\\"(\s*[,}\]\n])', r'"\1', re.sub(r'(:\s*)\\"', r'\1"', cleaned))
    for cand in (cleaned, lenient):
        try:
            d = json.loads(cand)
            if isinstance(d, dict):
                return d
        except json.JSONDecodeError:
            continue
    return {}


async def grade_with_ai(card: dict, transcript: str, rep_name: str, contact_name: str, direction: str, duration_s: int, industry: Optional[str] = None, language: Optional[str] = None, channel: str = "call") -> dict:
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY not set")
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(api_key=api_key, session_id=f"scorecard-{uuid.uuid4().hex[:12]}",
                   system_message=_grader_prompt(card, rep_name, contact_name, direction, duration_s, industry, language, channel)).with_model(*MODEL)
    resp = await asyncio.wait_for(chat.send_message(UserMessage(text=f"TRANSCRIPT:\n{transcript[:24000]}")), timeout=60.0)
    text = resp if isinstance(resp, str) else getattr(resp, "text", "") or ""
    data = _parse_json(text)
    if not data:
        logger.warning(f"[Scorecards] grader returned unparseable JSON, retrying once: {text[:160]!r}")
        resp = await asyncio.wait_for(chat.send_message(UserMessage(text="Your last reply was not valid JSON. Reply again with ONLY the JSON object, no prose, no escaped quotes around values.")), timeout=60.0)
        data = _parse_json(resp if isinstance(resp, str) else getattr(resp, "text", "") or "")
    if not data:
        raise ValueError("The grader did not return valid JSON")
    by_id = {str(r.get("id")): r for r in data.get("results") or [] if isinstance(r, dict)}
    results = []
    for c in card.get("criteria") or []:
        r = by_id.get(c["id"], {})
        p = r.get("passed")
        if isinstance(p, str):
            p = {"true": True, "false": False}.get(p.lower())
        try:
            conf = max(0.0, min(1.0, float(r.get("confidence") if r.get("confidence") is not None else 0.5)))
        except (TypeError, ValueError):
            conf = 0.5
        results.append({"criterion_id": c["id"], "text": c["text"], "critical": bool(c.get("critical")), "weight": int(c.get("weight") or 1),
                        "passed": p if p in (True, False) else None, "ai_passed": p if p in (True, False) else None,
                        "evidence": no_em_dash(str(r.get("evidence") or ""))[:200], "confidence": round(conf, 2), "override": None})
    return {
        "results": results,
        "summary": no_em_dash(str(data.get("summary") or "")).strip()[:900],
        "wins": [no_em_dash(str(w))[:220] for w in (data.get("wins") or []) if str(w).strip()][:3],
        "coaching": [no_em_dash(str(t))[:260] for t in (data.get("coaching") or []) if str(t).strip()][:4],
        "customer_sentiment": data.get("customer_sentiment") if data.get("customer_sentiment") in ("positive", "neutral", "negative") else "neutral",
        "call_type": data.get("call_type") if data.get("call_type") in ("conversation", "no_conversation") else "conversation",
    }


def serialize_eval(ev: dict) -> dict:
    out = {k: v for k, v in ev.items() if k != "_id"}
    out["id"] = str(ev["_id"])
    for k in ("created_at", "updated_at", "call_at", "alerts_sent_at", "acknowledged_at"):
        if k in out:
            out[k] = _iso(out[k])
    return out


def unread_coaching(evals: list) -> int:
    """Graded calls whose coaching the rep has not tapped 'Got it' on yet."""
    return sum(1 for e in evals if e.get("coaching") and not e.get("acknowledged_at"))


async def acknowledge(db, ev: dict, actor: dict) -> dict:
    """The rep read the coaching. Idempotent; managers see the stamp on the team board, the rep page and every alert."""
    if ev.get("acknowledged_at"):
        return ev
    upd = {"acknowledged_at": _now(), "acknowledged_by": str(actor["_id"])}
    await db[EVAL_COLL].update_one({"_id": ev["_id"]}, {"$set": upd})
    ev.update(upd)
    return ev


async def _conversation_for(db, log: dict) -> Optional[dict]:
    pend = await db.pending_calls.find_one({"call_sid": log.get("call_sid")}, {"conversation_id": 1}) if log.get("call_sid") else None
    cid = (pend or {}).get("conversation_id")
    if cid and ObjectId.is_valid(str(cid)):
        conv = await db.conversations.find_one({"_id": ObjectId(str(cid))})
        if conv:
            return conv
    if log.get("contact_id"):
        return await db.conversations.find_one({"contact_id": str(log["contact_id"]), "user_id": str(log.get("user_id") or "")},
                                               sort=[("last_message_at", -1)])
    return None


async def evaluate_call(call_sid: str, scorecard_id: Optional[str] = None, force: bool = False, actor_id: Optional[str] = None) -> Optional[dict]:
    """Grade one recorded call. Returns the stored evaluation, or None when the call is not gradable
    (no transcript, too short, voicemail, no scorecard applies)."""
    db = get_db()
    log = await db.call_logs.find_one({"call_sid": call_sid})
    if not log:
        return None
    existing = await db[EVAL_COLL].find_one({"call_sid": call_sid})
    if existing and not force:
        return existing
    transcript = (log.get("transcript") or "").strip()
    dur = int(log.get("duration_s") or 0)
    if not transcript or dur < MIN_DURATION_S or (log.get("outcome") in ("voicemail", "no_answer")):
        logger.info(f"[Scorecard] skip {call_sid}: transcript={bool(transcript)} dur={dur} outcome={log.get('outcome')}")
        return None
    rep = await db.users.find_one({"_id": _oid(log.get("user_id"))}) if _oid(log.get("user_id")) else None
    if not rep:
        return None
    conv = await _conversation_for(db, log)
    card = await db[COLL].find_one({"_id": _oid(scorecard_id)}) if scorecard_id else await pick_scorecard(db, rep, conv)
    if not card or not card.get("criteria"):
        logger.info(f"[Scorecard] no scorecard applies to {call_sid} (rep {rep.get('name')})")
        return None

    rep_name = _first(rep)
    contact_name = log.get("contact_name") or "the customer"
    from services import industries as ind
    from services import locales as loc
    industry = await ind.store_industry(db, card.get("store_id") or rep.get("store_id"))
    language = loc.dialect(await loc.store_locale(db, card.get("store_id") or rep.get("store_id")))
    graded = await grade_with_ai(card, _transcript_text(log, rep_name), rep_name, contact_name, log.get("direction") or "outbound", dur, industry, language)
    pct, misses = compute_score(graded["results"], card["criteria"])
    now = _now()
    doc = {
        "call_sid": call_sid, "user_id": str(rep["_id"]), "rep_name": rep.get("name") or rep_name, "store_id": user_store_id(rep),
        "contact_id": log.get("contact_id"), "contact_name": log.get("contact_name") or "", "conversation_id": str(conv["_id"]) if conv else None,
        "inbox_id": (conv or {}).get("inbox_id"), "scorecard_id": str(card["_id"]), "scorecard_name": card.get("name"), "department": card.get("department") or "",
        "duration_s": dur, "direction": log.get("direction") or "outbound", "call_at": log.get("timestamp") or log.get("created_at") or now,
        "results": graded["results"], "score_pct": pct, "critical_misses": misses, "summary": graded["summary"], "wins": graded["wins"],
        "coaching": graded["coaching"], "customer_sentiment": graded["customer_sentiment"], "call_type": graded["call_type"],
        "model": MODEL[1], "graded_by": "ai", "rescored_by": actor_id if force else None, "updated_at": now,
    }
    if existing:
        doc["created_at"] = existing.get("created_at") or now
        doc["alerts_sent_at"] = existing.get("alerts_sent_at")
        doc["alerted_user_ids"] = existing.get("alerted_user_ids") or []
        await db[EVAL_COLL].replace_one({"_id": existing["_id"]}, doc)
        doc["_id"] = existing["_id"]
    else:
        doc["created_at"] = now
        doc["alerts_sent_at"] = None
        doc["alerted_user_ids"] = []
        res = await db[EVAL_COLL].insert_one(doc)
        doc["_id"] = res.inserted_id
    await db.call_logs.update_one({"call_sid": call_sid}, {"$set": {"evaluation_id": str(doc["_id"]), "score_pct": pct, "scorecard_name": card.get("name")}})
    await db.messages.update_one({"call_sid": call_sid, "type": "call_log"}, {"$set": {"score_pct": pct, "evaluation_id": str(doc["_id"])}})
    if not existing:
        try:
            await send_alerts(db, doc, card, rep)
        except Exception as e:
            logger.warning(f"[Scorecard] alerts failed for {call_sid}: {e}")
    logger.info(f"[Scorecard] graded {call_sid}: {pct}% on '{card.get('name')}', critical misses={len(misses)}")
    return doc


def score_call_later(call_sid: str, delay: float = 2.0):
    """Fire-and-forget hook for the recording pipeline."""
    async def _run():
        await asyncio.sleep(delay)
        try:
            await evaluate_call(call_sid)
        except Exception as e:
            logger.warning(f"[Scorecard] grading failed for {call_sid}: {e}")
    asyncio.create_task(_run())


# ---------------------------------------------------------------- alerts
async def store_managers(db, store_id: Optional[str], exclude: Optional[str] = None) -> list:
    if not store_id:
        return []
    vals = [store_id] + ([ObjectId(store_id)] if ObjectId.is_valid(store_id) else [])
    q = {"role": {"$in": ["store_manager", "manager", "admin", "org_admin"]}, "status": {"$ne": "deactivated"},
         "$or": [{"store_id": {"$in": vals}}, {"store_ids": {"$in": vals}}]}
    users = await db.users.find(q, {"scorecard_muted_reps": 1, "timezone": 1}).to_list(50)
    if not users:
        store = await db.stores.find_one({"_id": _oid(store_id)}, {"organization_id": 1}) if _oid(store_id) else None
        if store and store.get("organization_id"):
            users = await db.users.find({"role": "org_admin", "organization_id": store["organization_id"], "status": {"$ne": "deactivated"}},
                                        {"scorecard_muted_reps": 1, "timezone": 1}).to_list(20)
    return [u for u in users if str(u["_id"]) != str(exclude or "")]


def _daytime(tz_name: Optional[str]) -> bool:
    try:
        from zoneinfo import ZoneInfo
        hour = datetime.now(ZoneInfo(tz_name or "America/Denver")).hour
    except Exception:
        hour = 12
    return 8 <= hour < 21


async def _notify(db, uid: str, ntype: str, title: str, body: str, link: str, ev_id: str, push: bool, icon: str = "clipboard"):
    idem = f"scorecard_{ntype}_{ev_id}_{uid}"
    r = await db.notifications.update_one({"idempotency_key": idem}, {"$setOnInsert": {
        "user_id": uid, "type": ntype, "priority": "urgent" if ntype == "scorecard_alert" else "normal", "title": title, "message": body,
        "link": link, "evaluation_id": ev_id, "idempotency_key": idem, "read": False, "dismissed": False, "created_at": _now()}}, upsert=True)
    if r.upserted_id and push:
        try:
            from routers.push_notifications import send_push_to_user
            asyncio.create_task(send_push_to_user(uid, title, body, link, icon))
        except Exception as e:
            logger.debug(f"[Scorecard] push failed: {e}")


async def send_alerts(db, ev: dict, card: dict, rep: dict) -> list:
    ev_id = str(ev["_id"])
    rep_id = str(rep["_id"])
    rep_first = _first(rep)
    contact = ev.get("contact_name") or "a customer"
    pct = ev.get("score_pct")
    missed_names = [r["text"] for r in ev.get("results") or [] if r["criterion_id"] in (ev.get("critical_misses") or [])]
    link = f"/scorecards/rep/{rep_id}?open={ev_id}"
    notified: list = []

    low = card.get("alert_below_pct") is not None and pct is not None and pct < int(card["alert_below_pct"])
    if (missed_names and card.get("alert_on_critical", True) is not False) or low:
        if missed_names:
            title = f"Missed critical: {rep_first} with {contact}"
            body = f"{' and '.join(missed_names[:2])}{' and more' if len(missed_names) > 2 else ''}. Scored {pct}% on {card.get('name')}."
        else:
            title = f"Low score: {rep_first} with {contact}"
            body = f"Scored {pct}% on {card.get('name')} (alert below {card.get('alert_below_pct')}%)."
        for m in await store_managers(db, ev.get("store_id"), exclude=rep_id):
            if rep_id in (m.get("scorecard_muted_reps") or []):
                continue
            await _notify(db, str(m["_id"]), "scorecard_alert", title, body, link, ev_id, push=_daytime(m.get("timezone")), icon="alert-circle")
            notified.append(str(m["_id"]))

    if card.get("notify_rep", True) is not False and pct is not None:
        passed = sum(1 for r in ev.get("results") or [] if r.get("passed") is True)
        graded = sum(1 for r in ev.get("results") or [] if r.get("passed") is not None)
        tip = (ev.get("coaching") or [""])[0]
        title = f"Call scored {pct}%: {contact}"
        body = f"{passed} of {graded} on {card.get('name')}." + (f" Tip: {tip}" if tip else "")
        await _notify(db, rep_id, "scorecard_result", title, body[:200], f"/scorecards/my?open={ev_id}", ev_id, push=True, icon="clipboard")

    await db[EVAL_COLL].update_one({"_id": ev["_id"]}, {"$set": {"alerts_sent_at": _now(), "alerted_user_ids": notified}})
    ev["alerted_user_ids"] = notified
    return notified


# ---------------------------------------------------------------- overrides
async def apply_override(db, ev: dict, criterion_id: str, passed, actor: dict, note: str = "") -> dict:
    results = ev.get("results") or []
    hit = next((r for r in results if r["criterion_id"] == criterion_id), None)
    if not hit:
        raise ValueError("Criterion not on this evaluation")
    if passed not in (True, False, None):
        raise ValueError("passed must be true, false or null")
    hit["passed"] = passed
    hit["override"] = None if passed == hit.get("ai_passed") else {"by": str(actor["_id"]), "by_name": _first(actor), "at": _iso(_now()), "note": (note or "")[:200]}
    card = await db[COLL].find_one({"_id": _oid(ev.get("scorecard_id"))})
    criteria = (card or {}).get("criteria") or [{"id": r["criterion_id"], "weight": r.get("weight", 1), "critical": r.get("critical")} for r in results]
    pct, misses = compute_score(results, criteria)
    upd = {"results": results, "score_pct": pct, "critical_misses": misses, "graded_by": "manager" if any(r.get("override") for r in results) else "ai", "updated_at": _now()}
    await db[EVAL_COLL].update_one({"_id": ev["_id"]}, {"$set": upd})
    await db.call_logs.update_one({"call_sid": ev["call_sid"]}, {"$set": {"score_pct": pct}})
    await db.messages.update_one({"call_sid": ev["call_sid"], "type": "call_log"}, {"$set": {"score_pct": pct}})
    ev.update(upd)
    return ev


# ---------------------------------------------------------------- stats
def _week_start(d: datetime) -> datetime:
    d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    d = d.astimezone(timezone.utc)
    return (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def _avg(vals: list) -> Optional[int]:
    vals = [v for v in vals if v is not None]
    return int(round(sum(vals) / len(vals))) if vals else None


def _dt(ev: dict) -> datetime:
    v = ev.get("call_at") or ev.get("created_at")
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            v = _now()
    if not isinstance(v, datetime):
        v = _now()
    return v if v.tzinfo else v.replace(tzinfo=timezone.utc)


def criteria_rates(evals: list) -> list:
    """Pass rate per criterion across a set of evaluations (N/A excluded)."""
    agg: dict = {}
    for ev in evals:
        for r in ev.get("results") or []:
            key = r["criterion_id"]
            a = agg.setdefault(key, {"id": key, "text": r.get("text"), "critical": bool(r.get("critical")), "passed": 0, "graded": 0, "scorecard_id": ev.get("scorecard_id")})
            if r.get("passed") is None:
                continue
            a["graded"] += 1
            a["passed"] += 1 if r["passed"] else 0
    out = []
    for a in agg.values():
        a["pass_rate"] = int(round(100 * a["passed"] / a["graded"])) if a["graded"] else None
        out.append(a)
    out.sort(key=lambda a: (a["pass_rate"] if a["pass_rate"] is not None else 101, not a["critical"]))
    return out


def rep_stats(evals: list, days: int) -> dict:
    now = _now()
    cutoff = now - timedelta(days=days)
    prev_cut = cutoff - timedelta(days=days)
    cur = [e for e in evals if _dt(e) >= cutoff]
    prev = [e for e in evals if prev_cut <= _dt(e) < cutoff]
    weeks: dict = {}
    for e in cur:
        ws = _week_start(_dt(e))
        weeks.setdefault(ws, []).append(e.get("score_pct"))
    trend = [{"week_start": ws.isoformat(), "label": ws.strftime("%b %-d"), "avg": _avg(v), "count": len(v)} for ws, v in sorted(weeks.items())]
    return {
        "days": days, "count": len(cur), "avg_score": _avg([e.get("score_pct") for e in cur]), "prev_avg": _avg([e.get("score_pct") for e in prev]),
        "critical_misses": sum(len(e.get("critical_misses") or []) for e in cur),
        "clean_calls": sum(1 for e in cur if not e.get("critical_misses")), "trend": trend, "criteria": criteria_rates(cur),
        "unread_coaching": unread_coaching(cur), "acknowledged": sum(1 for e in cur if e.get("acknowledged_at")),
    }


async def team_stats(db, scope: dict, days: int, scorecard_id: Optional[str] = None) -> dict:
    cutoff = _now() - timedelta(days=days)
    q = {**scope, "call_at": {"$gte": cutoff}}
    if scorecard_id:
        q["scorecard_id"] = scorecard_id
    evals = await db[EVAL_COLL].find(q).sort("call_at", -1).to_list(3000)
    by_rep: dict = {}
    for e in evals:
        by_rep.setdefault(e["user_id"], []).append(e)
    ids = [ObjectId(u) for u in by_rep if ObjectId.is_valid(u)]
    users = {str(u["_id"]): u async for u in db.users.find({"_id": {"$in": ids}}, {"name": 1, "first_name": 1, "photo_url": 1, "photo_thumbnail": 1, "role": 1})} if ids else {}
    reps = []
    heat: dict = {}
    for uid, evs in by_rep.items():
        u = users.get(uid, {})
        rates = criteria_rates(evs)
        heat[uid] = {r["id"]: r["pass_rate"] for r in rates}
        reps.append({"user_id": uid, "name": u.get("name") or evs[0].get("rep_name") or "Rep", "photo": u.get("photo_thumbnail") or u.get("photo_url"),
                     "count": len(evs), "avg_score": _avg([e.get("score_pct") for e in evs]),
                     "critical_misses": sum(len(e.get("critical_misses") or []) for e in evs),
                     "unread_coaching": unread_coaching(evs), "acknowledged": sum(1 for e in evs if e.get("acknowledged_at")),
                     "last_call_at": _iso(evs[0].get("call_at")), "weakest": rates[0]["text"] if rates and rates[0]["pass_rate"] is not None and rates[0]["pass_rate"] < 100 else None})
    reps.sort(key=lambda r: (-(r["avg_score"] if r["avg_score"] is not None else -1), -r["count"]))
    alerts = [serialize_eval(e) for e in evals if e.get("critical_misses")][:30]
    return {
        "days": days, "scorecard_id": scorecard_id, "calls": len(evals), "avg_score": _avg([e.get("score_pct") for e in evals]),
        "critical_misses": sum(len(e.get("critical_misses") or []) for e in evals), "reps": reps, "unread_coaching": unread_coaching(evals),
        "criteria": criteria_rates(evals) if scorecard_id else [], "heatmap": heat if scorecard_id else {}, "alerts": alerts,
    }
