"""Mystery Shop Clients: the AI shopper calls people who are NOT app users (a client store's sales/service staff),
grades every call and rolls the results into a store report the client can open without logging in."""
import asyncio
import base64
import json
import logging
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from bson import ObjectId

from services import i18n
from services import industries as ind
from services import locales as loc
from services import scripts as scr
from services import scorecards as sc
from services import text_shops as tx
from services import email_shops as ems
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

MODES = ("phone", "text", "email")


def mode_of(channel: Optional[str]) -> str:
    return channel if channel in ("text", "email") else "phone"


def mode_q(mode: Optional[str]) -> dict:
    """Same-mode query: a person can be on one call, one text thread and one email thread at the same time."""
    m = mode_of(mode if mode in MODES else "phone")
    return {"mode": m} if m != "phone" else {"mode": {"$nin": ["text", "email"]}}

DEPARTMENTS = ind.dept_keys("automotive")  # automotive keys; use ind.* for anything industry-aware
DEPT_LABEL = ind.label_map()
ALL_DEPARTMENTS = ind.all_dept_keys()
CALL_STATUSES_OPEN = ["scheduled", "dialing", "live", "ending", "grading"]
DEFAULT_HOURS = {"start": "09:00", "end": "18:00", "days": [0, 1, 2, 3, 4, 5]}
ALWAYS_OPEN = {"start": "00:00", "end": "23:59", "days": [0, 1, 2, 3, 4, 5, 6]}

# Global challenge pool. Persona text uses {vehicle} and {store}; the client's brand fills them in at shop time.
STARTER_CHALLENGES = [
    {"slug": "shop_sales_availability", "department": "sales", "category": "Sales calls", "title": "Shopper: is it still available?", "runtime": "3 to 5 min",
     "purpose": "The classic phone-up. A shopper saw a unit online and calls to ask if it is still there. A great rep gets the name and number, sells the visit, never the price.",
     "body": "Answer with the store and your name. Get the caller's name early and use it.\n\nConfirm the exact vehicle and that it is available (or offer two alternatives).\n\n[Discovery, 2 questions max]\nWhat drew them to it? Anything to trade?\n\n[Never quote a payment on the phone]\nGive a reason: you would rather be right than fast with their money.\n\n[Set the appointment with two times]\nGet the best cell number in case you get disconnected. Recap and thank them.",
     "success_points": ["Answers with the store name and their own name", "Gets and uses the caller's name", "Confirms the vehicle and availability", "Asks about a trade-in", "Offers two appointment times", "Gets the caller's phone number", "Recaps and thanks the caller"],
     "persona": {"name": "Dana Whitfield", "voice": "female", "summary": "41, project manager, saw {vehicle} on {store}'s website last night. Friendly, a little rushed, comparing two stores.",
                 "goals": "Find out if it is still there and whether the drive is worth it. Will give a name and number if the rep earns it.",
                 "objections": ["Can you just tell me the payment over the phone?", "Is the online price negotiable?", "I'm comparing you with another store"],
                 "opening_line": "Hi, I'm calling about {vehicle} you have listed online, is it still available?"}},
    {"slug": "shop_sales_payment_first", "department": "sales", "category": "Sales calls", "title": "Shopper: payment before I drive over", "runtime": "3 to 5 min",
     "purpose": "The shopper wants a monthly payment quoted over the phone. A great rep acknowledges, explains why a blind quote hurts the customer, and sells the visit.",
     "body": "Acknowledge the question, do not dodge it. Explain that trade, credit tier and term change the number, so a phone quote would be a guess.\n\nAsk what they are working with: trade, down payment range, how soon they want to drive it.\n\nOffer a firm appointment with two times and a specific promise: exact numbers in 20 minutes.\n\nGet the name and cell number. Recap.",
     "success_points": ["Acknowledges the payment question without dodging", "Explains why a phone quote would be a guess", "Asks about a trade-in", "Asks about timeline", "Offers two appointment times", "Gets the caller's name and number"],
     "persona": {"name": "Marcus Bell", "voice": "male", "summary": "34, warehouse supervisor, budget driven. Looking at {vehicle} at {store}. Direct, a bit impatient.",
                 "goals": "Get a monthly payment number before agreeing to anything. Will book if the rep gives a real reason and a specific plan.",
                 "objections": ["I don't want to waste a trip, just give me a ballpark", "The other store gave me a number over the phone", "I'm not filling out a credit app until I know the payment"],
                 "opening_line": "Hi, I'm looking at {vehicle} on your site. What would the monthly payment be on that?"}},
    {"slug": "shop_sales_trade", "department": "sales", "category": "Sales calls", "title": "Shopper: what's my trade worth?", "runtime": "3 to 4 min",
     "purpose": "The shopper leads with their trade. A great rep gathers the facts, never guesses a number, and gets the car on the lot.",
     "body": "Ask the facts: year, make, model, mileage, condition, payoff, keys. Never guess a number over the phone.\n\nAsk what they are replacing it with and confirm the unit they are interested in.\n\nSet the appraisal appointment with two times. Tell them what to bring (title or payoff letter). Get the cell number.",
     "success_points": ["Asks mileage, condition and payoff", "Does not guess a trade number over the phone", "Connects the trade to the vehicle they want", "Offers two appointment times", "Tells them what to bring", "Gets the caller's phone number"],
     "persona": {"name": "Priya Raman", "voice": "female", "summary": "29, nurse, owns a 2019 Honda CR-V with 61,000 miles, one small fender bender repaired. Interested in {vehicle} at {store}. Careful, wants a fair number.",
                 "goals": "Get a real trade value. Will come in if the rep explains the process and gives a time.",
                 "objections": ["Carvana gave me a number online in two minutes", "Can you at least give me a range?", "I don't want to sit at a dealership all day"],
                 "opening_line": "Hi, I've got a CR-V I'm thinking about trading in on {vehicle}. Can you tell me what it's worth?"}},
    {"slug": "shop_sales_price_match", "department": "sales", "category": "Objections", "title": "Shopper: the other store is cheaper", "runtime": "3 to 4 min",
     "purpose": "A shopper has a competing quote and wants you to beat it. A great rep stays calm, asks what the quote includes, and earns the visit.",
     "body": "Thank them for the honesty. Ask what the other quote includes: out the door, fees, trade, add-ons.\n\nDo not trash the competitor. Ask them to send the quote so you can compare apples to apples.\n\nOffer a specific appointment with two times and a promise: an honest answer on whether you can match it.",
     "success_points": ["Stays calm and thanks the caller", "Asks what the competing quote includes", "Does not badmouth the competitor", "Asks for the quote in writing", "Offers two appointment times", "Gets the caller's name and number"],
     "persona": {"name": "Tom Gerlach", "voice": "older", "summary": "58, retired, shopping {vehicle} at {store} and at a store across town that quoted 900 dollars less. Polite but firm, likes to negotiate.",
                 "goals": "Get a better price or a good reason to pick this store. Will book if the rep is honest and specific.",
                 "objections": ["Why should I drive to you if they're cheaper?", "Just match it and I'll come in today", "I've bought six cars, I know how this works"],
                 "opening_line": "Hi, I'm calling about {vehicle}. The dealer across town quoted me about nine hundred less on the same thing, can you beat that?"}},
    {"slug": "shop_sales_just_looking", "department": "sales", "category": "Sales calls", "title": "Shopper: just looking, early in the process", "runtime": "2 to 4 min",
     "purpose": "A soft, early shopper with lots of questions and no urgency. A great rep is helpful, asks discovery questions, and still asks for the visit and the number.",
     "body": "Be genuinely helpful. Ask what they are comparing and what matters most (space, mileage, budget, features).\n\nOffer a low pressure next step: come drive it, no commitment. Two times.\n\nGet the name and cell so you can text photos or a walkaround video.",
     "success_points": ["Asks what they are comparing", "Asks what matters most to them", "Offers a low pressure test drive with two times", "Offers to text photos or a video", "Gets the caller's name and number"],
     "persona": {"name": "Kelly Nguyen", "voice": "young", "summary": "26, first time buying from a dealer, saw {vehicle} at {store}. Curious, asks a lot of questions, no rush.",
                 "goals": "Learn without being pressured. Will give a number for photos if the rep is easy to talk to.",
                 "objections": ["I'm just looking right now", "I'm not ready to come in yet", "How is it different from the one at the other lot?"],
                 "opening_line": "Hi, I'm kind of early in my search but I saw {vehicle} on your site. Can you tell me a little about it?"}},
    {"slug": "shop_service_appointment", "department": "service", "category": "Service", "title": "Service caller: book an oil change", "runtime": "2 to 4 min",
     "purpose": "The everyday service call. A great advisor confirms the vehicle, offers the first available time, mentions transportation options and recaps.",
     "body": "Answer with the department and your name. Get the caller's name and the vehicle (year, make, model or mileage).\n\nAsk what they are noticing beyond the oil change.\n\nOffer the first available appointment, then an alternative. Mention shuttle, loaner or waiting area.\n\nConfirm the phone number for the reminder text and recap day, time and what to bring.",
     "success_points": ["Answers with the department and their name", "Confirms the vehicle", "Asks about other concerns", "Offers the first available time", "Mentions shuttle, loaner or waiting area", "Confirms the phone number", "Recaps the appointment"],
     "persona": {"name": "Angela Ruiz", "voice": "female", "summary": "45, teacher, drives {vehicle}, due for an oil change and a tire rotation. Pleasant, busy after school hours.",
                 "goals": "Get booked at a time that fits and know how long it takes.",
                 "objections": ["How long is that going to take?", "Do you have anything after 4?", "Is it cheaper at the quick lube place?"],
                 "opening_line": "Hi, I need to get an oil change scheduled on {vehicle}. What do you have this week?"}},
    {"slug": "shop_service_warning_light", "department": "service", "category": "Service", "title": "Service caller: warning light just came on", "runtime": "3 to 4 min",
     "purpose": "A nervous customer with a check engine light. A great advisor reassures, asks the right questions, and gets the car in quickly.",
     "body": "Reassure first. Ask which light, whether it is flashing, and how the vehicle is driving.\n\nExplain what a diagnostic visit looks like and roughly how long. Ask about warranty coverage or mileage.\n\nOffer the soonest slot, mention transportation options, confirm the number and recap.",
     "success_points": ["Reassures the caller", "Asks whether the light is flashing and how it drives", "Explains the diagnostic step", "Asks about warranty or mileage", "Offers the soonest appointment", "Mentions transportation options", "Confirms the phone number"],
     "persona": {"name": "Derek Holloway", "voice": "male", "summary": "52, sales rep who drives a lot, check engine light came on this morning in {vehicle}. Worried about being without a car.",
                 "goals": "Know if it is safe to drive and get it looked at fast without losing a work day.",
                 "objections": ["Is it safe to keep driving it?", "I can't be without my car for a whole day", "How much is the diagnostic going to cost me?"],
                 "opening_line": "Hi, the check engine light just came on in {vehicle} this morning. Should I be worried, and how soon can you look at it?"}},
    {"slug": "shop_service_price_quote", "department": "service", "category": "Service", "title": "Service caller: how much for brakes?", "runtime": "2 to 4 min",
     "purpose": "A price shopper for a common repair. A great advisor gives a helpful range, explains what drives the price, and books an inspection.",
     "body": "Ask the vehicle and what they are noticing (noise, pulsing, mileage on the pads).\n\nGive an honest range and explain what changes it: pads only versus rotors, front versus rear.\n\nOffer a free or low cost inspection with a firm time, mention how long it takes, confirm the number.",
     "success_points": ["Confirms the vehicle", "Asks what they are noticing", "Gives an honest price range", "Explains what changes the price", "Offers an inspection appointment with a time", "Confirms the phone number"],
     "persona": {"name": "Lisa Ferraro", "voice": "female", "summary": "38, small business owner, hears a grinding noise when braking in {vehicle}. Practical, comparing prices with an independent shop.",
                 "goals": "Get a real price and decide where to go. Will book if the advisor is straight with her.",
                 "objections": ["The shop down the street quoted me four hundred", "Can't you just give me a number?", "Do I really need rotors too?"],
                 "opening_line": "Hi, I'm hearing a grinding noise when I brake on {vehicle}. Can you tell me what brakes would run me?"}},
    {"slug": "shop_service_recall", "department": "service", "category": "Service", "title": "Service caller: recall notice in the mail", "runtime": "2 to 3 min",
     "purpose": "A customer got a recall letter. A great advisor confirms the VIN or vehicle, explains the fix is no charge, and books it while checking for other needs.",
     "body": "Ask for the vehicle and, if possible, the VIN or the recall number on the letter.\n\nExplain that recall work is no charge and roughly how long it takes. Ask about anything else the vehicle needs while it is in.\n\nOffer two times, mention transportation options, confirm the number and recap.",
     "success_points": ["Asks for the vehicle or VIN", "Confirms the recall is no charge", "Explains how long it takes", "Asks about other service needs", "Offers two appointment times", "Confirms the phone number"],
     "persona": {"name": "George Patel", "voice": "older", "summary": "64, retired engineer, got a recall letter for {vehicle}. Methodical, wants clear answers.",
                 "goals": "Get the recall handled and understand what is involved.",
                 "objections": ["Do I have to pay anything for this?", "How long will you need the car?", "Can you do the oil change at the same time?"],
                 "opening_line": "Hello, I received a recall notice for {vehicle}. I'd like to get that taken care of."}},
    # ── Parts counter ──
    {"slug": "shop_parts_in_stock", "department": "parts", "category": "Parts", "title": "Parts caller: do you have it in stock?", "runtime": "2 to 4 min",
     "purpose": "The everyday parts call. A great counterperson pins down the exact vehicle, checks availability, quotes one clear number and asks for the sale or a hold.",
     "body": "Answer with the parts department and your name. Get the caller's name.\n\nConfirm the exact vehicle: year, model, trim, or better, the VIN. Explain why it matters (right part the first time).\n\nCheck availability and say what you found: on the shelf, or how fast it arrives.\n\nQuote one clear price and what it includes (core charge, tax). Ask to set it aside or order it. Get the cell number for the ready call and recap.",
     "success_points": ["Answers with the department and their name", "Gets the caller's name", "Confirms year, trim or VIN before quoting", "States availability clearly", "Quotes one clear price with what it includes", "Offers to hold or order the part", "Gets the phone number and recaps"],
     "persona": {"name": "Ray Dominguez", "voice": "male", "summary": "47, does his own brakes on weekends, needs front pads and rotors for {vehicle}. Friendly, practical, in a bit of a hurry on a lunch break.",
                 "goals": "Find out if the parts are on the shelf and what they cost. Will hold them if the counterperson is quick and clear.",
                 "objections": ["I don't have the VIN on me, it's the regular one", "Can you just tell me the price?", "How does that compare to the parts store?"],
                 "opening_line": "Hi, I'm looking for front brake pads and rotors for {vehicle}. Do you have those in stock?"}},
    {"slug": "shop_parts_cheaper_online", "department": "parts", "category": "Parts", "title": "Parts caller: I found it cheaper online", "runtime": "2 to 4 min",
     "purpose": "A price shopper with an online quote. A great counterperson stays friendly, sells fit and warranty without knocking aftermarket, and still asks for the sale.",
     "body": "Thank them for checking with you. Confirm the vehicle and the exact part so you are comparing the same thing.\n\nAsk what the online price includes: shipping, core, return policy, is it the genuine part or aftermarket.\n\nExplain the OEM advantage in one breath: fit, warranty, it is the part the vehicle came with, and you can have it today. Never trash the other seller.\n\nAsk for the sale or offer to hold it. Get the number.",
     "success_points": ["Stays friendly about the online price", "Confirms the vehicle and exact part", "Asks what the online price includes", "Explains fit and warranty without knocking aftermarket", "Asks for the sale or offers a hold", "Gets the caller's name and number"],
     "persona": {"name": "Jenna Kowalski", "voice": "female", "summary": "33, budget minded, found a side mirror assembly for {vehicle} online for about 40 dollars less than she expects the dealer to charge. Polite, direct, has the tab open.",
                 "goals": "See if the store will come close or give a real reason to pay more. Will buy local if the answer is honest and quick.",
                 "objections": ["The website has it for 40 less with free shipping", "Is the aftermarket one really any different?", "Why should I pay more to pick it up?"],
                 "opening_line": "Hi, I need a driver side mirror for {vehicle}. I found one online pretty cheap, can you match that or what would yours run?"}},
    {"slug": "shop_parts_not_sure", "department": "parts", "category": "Parts", "title": "Parts caller: car is on a lift, not sure which part", "runtime": "3 to 4 min",
     "purpose": "An urgent caller who does not know the exact part. A great counterperson asks the right questions, gets the VIN, and finds a way to get it in their hands today.",
     "body": "Slow them down kindly. Get the caller's name and where the vehicle is.\n\nAsk for the VIN (registration, insurance card, door jamb) so you can look up the exact part. Ask what the mechanic said is wrong.\n\nCheck availability. If it is not on the shelf, offer the fastest path: another store, overnight, or a will-call time.\n\nQuote clearly, offer to hold or order, get the cell number, recap when it will be ready.",
     "success_points": ["Gets the caller's name", "Asks for the VIN or how to find it", "Asks what the mechanic diagnosed", "Checks availability and offers the fastest option", "Quotes clearly", "Offers to hold or order", "Gets the phone number and recaps timing"],
     "persona": {"name": "Carla Mendes", "voice": "female", "summary": "39, {vehicle} is on a lift at an independent shop across town. The mechanic said it needs a water pump and maybe a thermostat housing. Stressed, needs the car for work tomorrow.",
                 "goals": "Get the right part today so the shop can finish. Will read the VIN off her insurance card if asked.",
                 "objections": ["I don't know the exact year, it's the one before the redesign I think", "Can you deliver it or do I have to come get it?", "The mechanic said any brand would work"],
                 "opening_line": "Hi, my car is up on a lift at a shop right now and they said it needs a water pump. It's {vehicle}, can you tell me if you have one?"}},
    # ── Rental desk ──
    {"slug": "shop_rental_insurance", "department": "rental", "category": "Rental", "title": "Rental caller: insurance is paying, car is in the body shop", "runtime": "3 to 4 min",
     "purpose": "The most common rental call. A great agent learns the claim details, explains direct billing plainly, offers a specific vehicle and books the pickup.",
     "body": "Answer with the rental department and your name. Get the caller's name and how they are doing after the accident.\n\nAsk which insurance company and whether they have a claim number and a daily allowance. Explain direct billing and what happens if the rate is above the allowance.\n\nAsk what they need: seats, cargo, how long. Offer a specific vehicle. Explain the requirements: license, card for the deposit, age.\n\nAsk to reserve it, set a pickup time, get the cell number, recap.",
     "success_points": ["Answers with the department and their name", "Asks about the insurance company and claim number", "Explains direct billing and the daily allowance", "Asks about seating and cargo needs", "Offers a specific vehicle", "Explains license, deposit and age requirements", "Sets a pickup time and gets the phone number"],
     "persona": {"name": "Monica Tran", "voice": "female", "summary": "36, two kids, her car was rear ended yesterday and is going to the body shop. Insurance said they cover a rental up to a daily limit. Needs {vehicle} or similar, with room for a car seat, today.",
                 "goals": "Get a car today without paying out of pocket. Will book if the agent explains the insurance part clearly.",
                 "objections": ["Do I have to pay anything or does insurance handle it?", "I need it today, my car is my only way to work", "Will a car seat fit in that?"],
                 "opening_line": "Hi, my car got hit yesterday and my insurance said I can get a rental while it's in the shop. Do you do that?"}},
    {"slug": "shop_rental_weekend_trip", "department": "rental", "category": "Rental", "title": "Rental caller: SUV for a weekend trip", "runtime": "2 to 4 min",
     "purpose": "A retail rental. A great agent nails the dates and the need, states the rate with what it includes, and asks to reserve it.",
     "body": "Get the caller's name, pickup date, return date and where they are headed.\n\nAsk about people and luggage. Offer a specific vehicle that fits.\n\nState the daily rate and what it includes: mileage, fuel, insurance options, deposit. Ask about the driver's age and a second driver.\n\nAsk to reserve it and confirm the pickup time. Get the cell number and recap.",
     "success_points": ["Gets the dates and destination", "Asks about people and luggage", "Offers a specific vehicle", "States the rate and what it includes", "Explains mileage, deposit and age rules", "Asks to reserve it", "Gets the phone number and recaps"],
     "persona": {"name": "Devin Okafor", "voice": "male", "summary": "28, taking three friends to a national park Friday to Sunday, wants {vehicle} or a comparable SUV. Easygoing, cares about mileage limits and the deposit.",
                 "goals": "Lock in something roomy for the weekend and know the real total. Will reserve if the number is clear.",
                 "objections": ["Is there a mileage limit? We're driving about 600 miles", "How much is the deposit and when do I get it back?", "I'm 28, is there a young driver fee?"],
                 "opening_line": "Hi, I'm looking to rent an SUV for a weekend trip, Friday through Sunday. Do you have something like {vehicle} available?"}},
    {"slug": "shop_rental_service_loaner", "department": "rental", "category": "Rental", "title": "Rental caller: need a car while mine is in service", "runtime": "2 to 3 min",
     "purpose": "A service customer asking about a loaner or a rental. A great agent checks whether the repair qualifies for a loaner, explains the paid option plainly, and coordinates with service.",
     "body": "Get the caller's name and the service appointment details. Ask whether their repair is warranty work, which may qualify for a loaner.\n\nIf a loaner is not available, explain the rental option: rate, what it includes, requirements.\n\nOffer to reserve it for the appointment time and coordinate with the advisor. Get the cell number and recap.",
     "success_points": ["Gets the caller's name and appointment details", "Asks whether the repair is warranty work", "Explains loaner versus paid rental clearly", "States the rate and requirements", "Offers to coordinate with the service advisor", "Gets the phone number and recaps"],
     "persona": {"name": "Harold Finch", "voice": "older", "summary": "61, has {vehicle} booked for a transmission repair on Thursday and expects it to take a few days. Courteous, a little annoyed about being without a car.",
                 "goals": "Find out if he gets a loaner for free and, if not, what a rental costs. Will book if the agent makes it simple.",
                 "objections": ["Shouldn't a loaner be free when it's a warranty repair?", "Why do I need a credit card if the dealership already has my information?", "Can you just have it ready when I drop off?"],
                 "opening_line": "Hi, I have {vehicle} coming in for service on Thursday and they said it might be a few days. Can I get a loaner, or what would a rental cost?"}},
    # ── Body shop / collision center ──
    {"slug": "shop_collision_parking_lot", "department": "collision", "category": "Body Shop", "title": "Collision caller: someone hit my car in a parking lot", "runtime": "3 to 4 min",
     "purpose": "The classic first call after a fender bender. A great estimator leads with empathy, gets the vehicle, damage and claim details, books the estimate and mentions the rental.",
     "body": "Answer with the body shop and your name. Ask if everyone is okay before anything else.\n\nConfirm the vehicle, where the damage is and whether it drives straight with no lights on.\n\nAsk whose insurance is handling it and whether a claim number exists. Explain the next step: an estimate in person (or photos to start), how long it takes, and that the real number comes after teardown.\n\nMention rental coordination. Offer two estimate times, get the cell number, recap what to bring.",
     "success_points": ["Shows empathy about the accident", "Confirms the vehicle and damage location", "Asks whether it is drivable", "Asks which insurance and whether a claim is open", "Explains the estimate process without quoting blind", "Mentions rental or transportation", "Offers two estimate times and gets the phone number"],
     "persona": {"name": "Nicole Barrett", "voice": "female", "summary": "42, came out of the grocery store to find the rear quarter panel of {vehicle} dented and the tail light cracked. The other driver left a note and insurance info. Shaken but organized.",
                 "goals": "Understand what happens next and get the car looked at this week. Will book if the estimator is calm and specific.",
                 "objections": ["Do I go through my insurance or theirs?", "Can you give me a rough number so I know if it's worth a claim?", "Will I need a rental? It's my only car"],
                 "opening_line": "Hi, somebody hit {vehicle} in a parking lot and left a note. I've never done this before, what do I do?"}},
    {"slug": "shop_collision_phone_quote", "department": "collision", "category": "Body Shop", "title": "Collision caller: can you quote it from photos?", "runtime": "2 to 4 min",
     "purpose": "A caller wants a price over the phone. A great estimator explains why a blind number would hurt them, offers a fast in-person estimate, and asks about the deductible and parts.",
     "body": "Acknowledge the question, do not dodge it. Explain that hidden damage behind a bumper changes the number, so a phone quote would be a guess that could hurt them with insurance.\n\nOffer photos as a starting point and a 20 minute in-person estimate with two times.\n\nAsk if they are paying out of pocket or through a claim, and what their deductible is. Explain original versus aftermarket parts and your warranty.\n\nGet the cell number and recap.",
     "success_points": ["Acknowledges the price question without dodging", "Explains why a phone quote would be a guess", "Offers a quick in-person estimate with two times", "Asks about a claim and the deductible", "Explains parts and warranty", "Gets the caller's name and number"],
     "persona": {"name": "Brian Castellano", "voice": "male", "summary": "50, backed {vehicle} into a post, bumper cracked and a dent above it. Thinking about paying cash instead of filing a claim. Impatient, wants a number to decide.",
                 "goals": "Get a ballpark to decide claim versus cash. Will come in if the estimator gives a real reason and a quick time.",
                 "objections": ["I can text you photos right now, just give me a range", "My deductible is 1000, is it even worth a claim?", "Do you use real parts or the cheap ones?"],
                 "opening_line": "Hi, I cracked the bumper on {vehicle}. Can I just text you a couple pictures and get a price?"}},
    {"slug": "shop_collision_insurance_steer", "department": "collision", "category": "Body Shop", "title": "Collision caller: my insurance says I have to use their shop", "runtime": "3 to 4 min",
     "purpose": "A customer who thinks they have no choice. A great estimator explains the right to choose respectfully, describes how the shop works with the insurer, and earns the estimate.",
     "body": "Thank them for calling and show empathy. Confirm the vehicle and damage.\n\nExplain, without bashing the insurance company, that the customer chooses the repair shop and that you work with their carrier directly: estimates, supplements, direct billing.\n\nExplain your warranty and how you keep them updated. Mention rental coordination.\n\nOffer two estimate times, get the cell number and the claim number, recap.",
     "success_points": ["Shows empathy and confirms the vehicle and damage", "Explains the right to choose the shop respectfully", "Describes working with the insurer directly", "Mentions the repair warranty", "Mentions rental coordination", "Offers two estimate times and gets the phone number"],
     "persona": {"name": "Patricia Lindqvist", "voice": "older", "summary": "57, {vehicle} was sideswiped and her insurance adjuster listed two preferred shops, neither of which is you. She has heard good things about your store. Polite, cautious, does not want to do anything that voids coverage.",
                 "goals": "Find out if she can use this shop without trouble from insurance. Will book if the estimator is confident and kind.",
                 "objections": ["The adjuster said I have to use one of their shops", "Will my insurance still pay if I come to you?", "How long is this going to take? Last time it was six weeks"],
                 "opening_line": "Hi, my insurance company gave me a list of shops for {vehicle} and you weren't on it, but I'd rather come to you. Is that even allowed?"}},
]


def _now():
    return datetime.now(timezone.utc)


def _oid(v) -> ObjectId:
    return ObjectId(str(v))


def _tz(client: dict) -> ZoneInfo:
    try:
        return ZoneInfo(client.get("timezone") or "America/Denver")
    except Exception:
        return ZoneInfo("America/Denver")


def _hours(client: dict) -> dict:
    if client.get("demo"):
        return dict(ALWAYS_OPEN)  # Quick shops have no business hours: they dial the moment they are placed, any time of day
    h = {**DEFAULT_HOURS, **(client.get("hours") or {})}
    h["days"] = [int(d) for d in (h.get("days") or DEFAULT_HOURS["days"])]
    return h


def _hm(v: str, fallback: str) -> tuple:
    try:
        hh, mm = (v or fallback).split(":")
        return int(hh), int(mm)
    except Exception:
        return tuple(int(x) for x in fallback.split(":"))


async def ensure_challenges(db) -> int:
    n = 0
    for tpl in STARTER_CHALLENGES:
        res = await db.scripts.update_one(
            {"slug": tpl["slug"], "pool": "mystery_shop", "shop_client_id": None},
            {"$setOnInsert": {**tpl, "kind": "phone", "pool": "mystery_shop", "industry": "automotive", "store_id": None, "shop_client_id": None, "direction": "inbound", "active": True, "created_at": _now(), "updated_at": _now()}}, upsert=True)
        n += 1 if res.upserted_id else 0
    await db.scripts.update_many({"pool": "mystery_shop", "industry": {"$exists": False}}, {"$set": {"industry": "automotive"}})
    return n


def offerings_of(client: dict) -> list:
    return [str(v).strip() for v in (client.get("offerings") or client.get("vehicles") or []) if str(v).strip()]


def plan_per_month(client: dict) -> dict:
    """Shops per department per month. New accounts store plan.per_month; the original automotive accounts stored sales_per_month / service_per_month."""
    plan = client.get("plan") or {}
    per = plan.get("per_month")
    if isinstance(per, dict) and per:
        return {k: int(v or 0) for k, v in per.items()}
    return {k: int(plan.get(f"{k}_per_month") or 0) for k in ind.dept_keys(ind.key_of(client)) if plan.get(f"{k}_per_month") is not None}


def plan_text_per_month(client: dict) -> dict:
    """Text (SMS) shops per department, on top of the calls."""
    per = ((client.get("plan") or {}).get("text_per_month")) or {}
    return {k: int(v or 0) for k, v in per.items()} if isinstance(per, dict) else {}


def plan_email_per_month(client: dict) -> dict:
    """Email shops per department, on top of the calls and texts."""
    per = ((client.get("plan") or {}).get("email_per_month")) or {}
    return {k: int(v or 0) for k, v in per.items()} if isinstance(per, dict) else {}


def terms_per_month(t: dict) -> dict:
    per = (t or {}).get("per_month")
    if isinstance(per, dict) and per:
        return {k: int(v or 0) for k, v in per.items()}
    return {k: int((t or {}).get(f"{k}_per_month") or 0) for k in ("sales", "service") if (t or {}).get(f"{k}_per_month")}


def invoice_extras(client: dict) -> dict:
    """Locale-aware Stripe invoice options: iDEAL + SEPA for euro accounts, a reverse-charge footer when the client gave a VAT id."""
    lc = loc.key_of(client)
    cur = loc.currency(lc)
    out: dict = {}
    if cur == "eur":
        out["payment_settings"] = {"payment_method_types": ["card", "ideal", "sepa_debit"]}
    elif cur == "gbp":
        out["payment_settings"] = {"payment_method_types": ["card", "bacs_debit"]}
    vat = (client.get("vat_id") or "").strip()
    if vat and cur in ("eur", "gbp"):
        out["custom_fields"] = [{"name": "VAT ID" if loc.language(lc) == "en" else "Btw-nummer", "value": vat[:40]}]
        out["footer"] = ("VAT reverse-charged to the customer (Article 196 EU VAT Directive)." if loc.language(lc) == "en" else "Btw verlegd naar de afnemer (artikel 196 Btw-richtlijn).")
    return out


def per_month_text_for(per: dict, locale: Optional[str], joiner: str = " + ") -> str:
    """'4 verkoop, 2 werkplaats en 1 schadeherstel' for a Dutch client; English otherwise."""
    if loc.dialect(locale) == "en":
        return per_month_text(per, joiner)
    parts = [f"{n} {ind.dept_label_for(k, locale).lower()}" for k, n in per.items() if int(n or 0) > 0]
    if joiner.strip() in ("en", "and") and len(parts) > 2:
        return ", ".join(parts[:-1]) + f"{joiner}{parts[-1]}"
    return joiner.join(parts) if parts else "0"


def per_month_text(per: dict, joiner: str = " + ") -> str:
    parts = [f"{n} {ind.dept_label(k).lower()}" for k, n in per.items() if int(n or 0) > 0]
    if joiner.strip() == "and" and len(parts) > 2:
        return ", ".join(parts[:-1]) + " and " + parts[-1]
    return joiner.join(parts) if parts else "0"


# ---------------------------------------------------------------- clients + people
def serialize_client(c: dict, extra: Optional[dict] = None) -> dict:
    lc = loc.key_of(c)
    out = {"id": str(c["_id"]), "name": c.get("name", ""), "brand": c.get("brand", ""), "city": c.get("city", ""), "state": c.get("state", ""), "timezone": c.get("timezone") or loc.get(lc)["timezone"],
           "locale": lc, "language": loc.get(lc)["language"], "currency": loc.get(lc)["currency"], "currency_symbol": loc.get(lc)["symbol"], "country": loc.get(lc)["country"], "locale_label": loc.get(lc)["label"], "vat_id": c.get("vat_id", ""),
           "number_state": {"own": bool((c.get("number") or {}).get("sid")), "needs_local_number": loc.get(lc)["country"] != "US" and not c.get("from_number"), "error": (c.get("number_error") or {}).get("error")},
           "contact_name": c.get("contact_name", ""), "contact_email": c.get("contact_email", ""), "contact_phone": c.get("contact_phone", ""), "contact_title": c.get("contact_title", ""),
           "plan": {"per_month": plan_per_month(c), "text_per_month": plan_text_per_month(c), "email_per_month": plan_email_per_month(c), "sales_per_month": plan_per_month(c).get("sales", 0), "service_per_month": plan_per_month(c).get("service", 0), "price_monthly": float((c.get("plan") or {}).get("price_monthly") or 0)},
           "industry": ind.key_of(c), "industry_label": ind.get(ind.key_of(c))["label"], "departments": ind.dept_options(ind.key_of(c)), "offering": ind.get(ind.key_of(c))["offering"], "customer_noun": ind.get(ind.key_of(c))["customer"],
           "hours": _hours(c), "vehicles": offerings_of(c), "offerings": offerings_of(c), "active": c.get("active", True), "record_calls": c.get("record_calls", True), "notes": c.get("notes", ""),
           "from_number": c.get("from_number") or "", "report_token": c.get("report_token"), "scorecards": c.get("scorecards") or {}, "billing": c.get("billing") or {},
           "demo": bool(c.get("demo")), "text_scorecards": bool(c.get("text_scorecards")),
           "created_at": c.get("created_at").isoformat() if c.get("created_at") else None}
    if extra:
        out.update(extra)
    return out


def serialize_target(t: dict, extra: Optional[dict] = None) -> dict:
    cc = t.get("contact_card") or {}
    out = {"id": str(t["_id"]), "client_id": t.get("client_id"), "name": t.get("name", ""), "phone": t.get("phone", ""), "email": t.get("email", ""), "department": t.get("department", "sales"), "department_label": ind.dept_label(t.get("department")), "title": t.get("title", ""),
           "notes": t.get("notes", ""), "active": t.get("active", True), "challenge_history": t.get("challenge_history") or [], "created_at": t.get("created_at").isoformat() if t.get("created_at") else None,
           "contact_card_sent_at": cc["sent_at"].isoformat() if hasattr(cc.get("sent_at"), "isoformat") else None, "contact_card_ok": cc.get("ok"), "contact_card_error": cc.get("error")}
    if extra:
        out.update(extra)
    return out


def serialize_call(s: dict) -> dict:
    return {"id": str(s["_id"]), "client_id": s.get("client_id"), "target_id": s.get("target_id"), "target_name": s.get("rep_name"), "department": s.get("department"), "department_label": ind.dept_label(s.get("department")),
            "industry": s.get("industry") or ind.industry_of_dept(s.get("department")), "customer_noun": ind.get(s.get("industry") or ind.industry_of_dept(s.get("department")))["customer"], "status": s.get("status"),
            "outcome": s.get("outcome"), "fail_reason": s.get("fail_reason"), "script_id": s.get("script_id"), "script_title": s.get("script_title"), "persona_name": (s.get("persona") or {}).get("name"),
            "curveballs": s.get("curveballs") or [], "scheduled_for": s["scheduled_for"].isoformat() if s.get("scheduled_for") else None, "attempts": s.get("attempts", 0),
            "started_at": s["started_at"].isoformat() if s.get("started_at") else None, "ended_at": s["ended_at"].isoformat() if s.get("ended_at") else None,
            "score_pct": s.get("score_pct"), "adherence_pct": s.get("adherence_pct"), "evaluation_id": s.get("evaluation_id"), "recording_url": s.get("recording_url"),
            "recording_seconds": s.get("recording_seconds"), "turns": len(s.get("turns") or []), "manual": bool(s.get("manual")), "demo": bool(s.get("demo")),
            "score_url": f"{scr._app_url()}/shop-score/{s['score_token']}" if s.get("score_token") else None, "score_sms_status": s.get("score_sms_status"), "score_views": s.get("score_views") or 0,
            "channel": s.get("mode") if s.get("mode") in ("text", "email") else "call", "text": tx.stats(s) if s.get("mode") in ("text", "email") else None,
            "subject": s.get("subject") if s.get("mode") == "email" else None, "rep_email": s.get("rep_email") if s.get("mode") == "email" else None}


# ---------------------------------------------------------------- challenge rotation
def fill_persona(persona: dict, client: dict, department: str) -> dict:
    industry = ind.key_of(client)
    d = ind.dept(department, industry)
    pool = offerings_of(client) or d.get("defaults") or ["what you have listed online"]
    offering = random.choice(pool)
    low = offering.lower()
    lang = loc.language(loc.key_of(client))
    if lang == "nl":
        # Dutch articles: "de Golf" for sales, "mijn Golf" for workshop/parts/damage, "een Golf" for rental
        if not low.startswith(("de ", "een ", "mijn ", "onze ", "die ", "het ")):
            offering = f"{'een' if department == 'rental' else 'mijn' if department in ('service', 'parts', 'collision') else 'de'} {offering}"
    elif industry == "automotive":
        if department in ("sales", "rental") and not low.startswith(("the ", "a ", "an ", "that ")):
            offering = f"{'a' if department == 'rental' else 'the'} {offering}"
        elif department in ("service", "parts", "collision") and not low.startswith(("my ", "our ")):
            offering = f"my {offering}"
    elif not low.startswith(("the ", "a ", "an ", "my ", "our ", "your ", "that ")):
        offering = f"the {offering}"
    place = client.get("name") or (ind.translated(industry, loc.key_of(client))["place"] if lang == "nl" else f"the {ind.get(industry)['place']}")
    return {k: ind.fill_offering(v, offering, place) for k, v in (persona or {}).items()} | {"vehicle": offering, "offering": offering}


def language_filter(language: Optional[str]) -> dict:
    """English challenges predate the language field, so 'en' means missing-or-en."""
    return {"language": {"$in": [None, "en"]}} if (language or "en") == "en" else {"language": language}


async def challenge_pool(db, client_id: Optional[str], department: Optional[str] = None, industry: Optional[str] = None, language: Optional[str] = "en", approved_only: bool = False) -> list:
    await ensure_challenges(db)
    q = {"kind": "phone", "pool": "mystery_shop", "active": {"$ne": False}, "$or": [{"shop_client_id": None}, {"shop_client_id": client_id}], **language_filter(language)}
    if department:
        q["department"] = department
    elif industry:
        q["industry"] = industry
    if approved_only:
        q["review.status"] = {"$ne": "needs_review"}
    return await db.scripts.find(q).sort([("department", 1), ("title", 1)]).to_list(200)


CHALLENGE_LANGUAGE = {"en-IE": "en-GB"}  # Irish clients draw from the British library


def challenge_language(client: dict) -> str:
    d = loc.dialect(loc.key_of(client))
    return CHALLENGE_LANGUAGE.get(d, d)


async def pick_challenge(db, client: dict, target: dict) -> Optional[dict]:
    """A challenge this person has not had; once they have had them all, the one they had longest ago.
    Non-English clients draw from reviewer-approved challenges in their language; until any exist, the English library is used (the caller still speaks the client's language)."""
    lang = challenge_language(client)
    dept = target.get("department") or "sales"
    pool = await challenge_pool(db, str(client["_id"]), dept, language=lang, approved_only=(lang != "en"))
    if not pool and lang != "en":
        pool = await challenge_pool(db, str(client["_id"]), dept)
    if not pool:
        return None
    history = [str(x) for x in (target.get("challenge_history") or [])]
    fresh = [s for s in pool if str(s["_id"]) not in history]
    if fresh:
        return random.choice(fresh)
    order = {sid: i for i, sid in enumerate(history)}
    pool.sort(key=lambda s: order.get(str(s["_id"]), -1))
    return pool[0]


# ---------------------------------------------------------------- scheduling
def _local_window(client: dict, day: datetime) -> Optional[tuple]:
    h = _hours(client)
    if day.weekday() not in h["days"]:
        return None
    sh, sm = _hm(h.get("start"), "09:00")
    eh, em = _hm(h.get("end"), "18:00")
    start = day.replace(hour=sh, minute=sm, second=0, microsecond=0)
    end = day.replace(hour=eh, minute=em, second=0, microsecond=0)
    return (start, end) if end > start else None


def in_hours(client: dict, when: Optional[datetime] = None) -> bool:
    if client.get("demo"):
        return True
    local = (when or _now()).astimezone(_tz(client))
    win = _local_window(client, local)
    return bool(win and win[0] <= local <= win[1])


def next_slot(client: dict, after: datetime, min_gap_minutes: int = 90) -> datetime:
    """A random moment inside business hours, at least min_gap after `after` (retries) and never in the last 20 minutes of the day."""
    if client.get("demo"):
        return (after + timedelta(minutes=min_gap_minutes)).astimezone(timezone.utc)  # no window, no random spread: exactly when asked
    tz = _tz(client)
    local = after.astimezone(tz) + timedelta(minutes=min_gap_minutes)
    for i in range(14):
        day = (local + timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        win = _local_window(client, day)
        if not win:
            continue
        start = max(win[0], local) if i == 0 else win[0]
        end = win[1] - timedelta(minutes=20)
        if end <= start:
            continue
        secs = int((end - start).total_seconds())
        return (start + timedelta(seconds=random.randint(0, secs))).astimezone(timezone.utc)
    return (after + timedelta(days=1)).astimezone(timezone.utc)


def month_bounds(month: Optional[str], tz: ZoneInfo) -> tuple:
    """(start, end) of a YYYY-MM month in the client's timezone, as UTC."""
    now_local = _now().astimezone(tz)
    if month:
        y, m = (int(x) for x in month.split("-")[:2])
    else:
        y, m = now_local.year, now_local.month
    start = datetime(y, m, 1, tzinfo=tz)
    end = datetime(y + (m == 12), (m % 12) + 1, 1, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


async def create_shop_call(db, client: dict, target: dict, when: datetime, created_by: Optional[str] = None, manual: bool = False, script: Optional[dict] = None, mode: str = "phone") -> Optional[dict]:
    """mode 'phone' = the AI calls; 'text' = the AI texts like a lead; 'email' = the AI emails like an internet lead. Text and email threads are graded with reply speed by the clock, quality by AI."""
    script = script or await pick_challenge(db, client, target)
    if not script:
        return None
    mode = mode_of(mode)
    dept = target.get("department") or "sales"
    persona = fill_persona(script.get("persona") or {}, client, dept)
    industry = ind.key_of(client)
    pool_cb = [c for c in (script.get("curveballs") or []) if str(c).strip()] or ind.dept(dept, industry).get("curveballs", [])
    curve = random.sample(pool_cb, k=min(len(pool_cb), random.choice([0, 1, 1, 2])))
    now = _now()
    direction = script.get("direction") if script.get("direction") in ("inbound", "outbound") else "inbound"
    doc = {"kind": "mystery_shop", "mode": mode, "status": "scheduled", "user_id": None, "client_id": str(client["_id"]), "target_id": str(target["_id"]),
           "rep_name": target.get("name") or "", "rep_phone": target.get("phone"), "rep_email": (target.get("email") or "").strip().lower() or None, "department": dept, "industry": industry, "store_id": None, "store_name": client.get("name") or f"the {ind.get(industry)['place']}", "locale": loc.key_of(client),
           "script_id": str(script["_id"]), "script_title": script.get("title"), "script_slug": script.get("slug"), "direction": "inbound" if mode != "phone" else direction, "persona": persona, "curveballs": curve,
           "assignment_id": None, "scheduled_for": when, "attempts": 0, "max_attempts": 3, "manual": manual, "token": uuid.uuid4().hex, "turns": [],
           "created_by": created_by, "created_at": now, "updated_at": now}
    res = await db.roleplay_sessions.insert_one(doc)
    await db.shop_targets.update_one({"_id": target["_id"]}, {"$push": {"challenge_history": str(script["_id"])}})
    doc["_id"] = res.inserted_id
    return doc


async def plan_month(db, client: dict, month: Optional[str] = None, created_by: Optional[str] = None) -> dict:
    """Top the month up to the plan quota per department, spread over the remaining business days, rotating people evenly."""
    tz = _tz(client)
    start, end = month_bounds(month, tz)
    now = _now()
    per, text_per, email_per = plan_per_month(client), plan_text_per_month(client), plan_email_per_month(client)
    created = {k: 0 for k in ind.dept_keys(ind.key_of(client))}
    created_text = {k: 0 for k in ind.dept_keys(ind.key_of(client))}
    created_email = {k: 0 for k in ind.dept_keys(ind.key_of(client))}
    quotas = {"phone": per, "text": text_per, "email": email_per}
    made = {"phone": created, "text": created_text, "email": created_email}
    for dept, mode in [(d, m) for d in ind.dept_keys(ind.key_of(client)) for m in MODES]:
        quota = int(quotas[mode].get(dept) or 0)
        if quota <= 0:
            continue
        q = {"kind": "mystery_shop", "client_id": str(client["_id"]), "department": dept, "scheduled_for": {"$gte": start, "$lt": end}, "status": {"$ne": "canceled"}, **mode_q(mode)}
        existing = await db.roleplay_sessions.count_documents(q)
        missing = quota - existing
        targets = await db.shop_targets.find({"client_id": str(client["_id"]), "department": dept, "active": {"$ne": False}, **({"email": {"$nin": [None, ""]}} if mode == "email" else {})}).to_list(200)
        if missing <= 0 or not targets:
            continue
        counts = {}
        async for s in db.roleplay_sessions.find(q, {"target_id": 1}):
            counts[s.get("target_id")] = counts.get(s.get("target_id"), 0) + 1
        targets.sort(key=lambda t: counts.get(str(t["_id"]), 0))
        from_dt = max(now + timedelta(minutes=30), start)
        if from_dt >= end:
            continue
        slots = []
        for _ in range(missing * 3):
            cand = next_slot(client, from_dt + timedelta(seconds=random.randint(0, max(60, int((end - from_dt).total_seconds())))), min_gap_minutes=0)
            if from_dt <= cand < end:
                slots.append(cand)
        slots = sorted(slots)[:missing]
        if len(slots) < missing:
            slots += [next_slot(client, from_dt, min_gap_minutes=0) for _ in range(missing - len(slots))]
        for i, when in enumerate(slots):
            t = targets[i % len(targets)]
            if await create_shop_call(db, client, t, when, created_by=created_by, mode=mode):
                made[mode][dept] += 1
    return {**created, **({"text": created_text} if any(created_text.values()) else {}), **({"email": created_email} if any(created_email.values()) else {})}


# ---------------------------------------------------------------- placing + outcomes
SHOP_NUMBER_KEY = "mystery_shop_from_number"


async def saved_shop_number(db) -> Optional[dict]:
    """The number Forest picked (or bought) as the main Mystery Shop caller ID, if any."""
    row = await db.settings.find_one({"key": SHOP_NUMBER_KEY})
    return row if row and row.get("value") else None


async def default_from_number(db) -> str:
    row = await saved_shop_number(db)
    return (row or {}).get("value") or os.environ.get("MYSTERY_SHOP_FROM_NUMBER") or os.environ.get("TWILIO_PHONE_NUMBER", "")


async def from_number(db, client: Optional[dict]) -> str:
    """Per-client override first, then the saved default, then the platform number."""
    return (client or {}).get("from_number") or await default_from_number(db)


async def is_shop_number(db, phone: str) -> bool:
    """True when an inbound call/text hits a number we shop from (so it must never ring a real person)."""
    if not phone:
        return False
    row = await saved_shop_number(db)
    if row and row.get("value") == phone:
        return True
    return bool(await db.shop_clients.find_one({"from_number": phone}, {"_id": 1}))


# ---------------------------------------------------------------- contact card (the .vcf reps save so the shop number shows a name)
CONTACT_CARD_KEY = "mystery_shop_contact_card"
CONTACT_CARD_DEFAULT = {"name": "Mystery Shop", "org": "I'm On Social"}
MMS_COUNTRIES = ("US", "CA")


async def contact_card_settings(db) -> dict:
    row = await db.settings.find_one({"key": CONTACT_CARD_KEY}) or {}
    return {**CONTACT_CARD_DEFAULT, **{k: v for k, v in (row.get("value") or {}).items() if v}}


async def set_contact_card(db, name: str, org: str) -> dict:
    name, org = no_em_dash(name or "").strip()[:40], no_em_dash(org or "").strip()[:40]
    if not name:
        raise ValueError("Give the contact a name, for example Mystery Shop or Practice Call")
    await db.settings.update_one({"key": CONTACT_CARD_KEY}, {"$set": {"value": {"name": name, "org": org or CONTACT_CARD_DEFAULT["org"]}, "updated_at": datetime.now(timezone.utc)}}, upsert=True)
    return await contact_card_settings(db)


async def contact_token(db, client: dict) -> str:
    tok = client.get("contact_token")
    if not tok:
        tok = uuid.uuid4().hex
        await db.shop_clients.update_one({"_id": client["_id"]}, {"$set": {"contact_token": tok}})
        client["contact_token"] = tok
    return tok


def contact_urls(token: str) -> tuple:
    base = scr._app_url()
    return f"{base}/api/public/shop-contact/{token}", f"{base}/api/public/shop-contact/{token}.vcf"


def _vc(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _pretty_phone(p: str) -> str:
    d = (p or "").replace(" ", "")
    if d.startswith("+1") and len(d) == 12:
        return f"({d[2:5]}) {d[5:8]}-{d[8:]}"
    if d.startswith("+31") and len(d) >= 11:
        return f"+31 {d[3:5]} {d[5:]}" if d[3] == "9" else f"+31 {d[3]} {d[4:]}"
    if d.startswith("+44") and len(d) >= 12:
        return f"+44 {d[3:7]} {d[7:]}"
    return d


def _fold(line: str) -> str:
    """vCard 3.0 line folding: 75 octets max, continuation lines start with a space."""
    return line[:75] + "".join("\r\n " + line[i:i + 74] for i in range(75, len(line), 74))


def contact_vcard(card: dict, phone: str, client: Optional[dict]) -> str:
    """vCard 3.0 with the logo embedded, so the shop number shows up named on every call and text."""
    lang = loc.dialect(loc.key_of(client)) if client else "en"
    note = i18n.t(lang, "vcf.note", store=client["name"]) if client else i18n.t(lang, "vcf.note_generic")
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"N:;{_vc(card['name'])};;;", f"FN:{_vc(card['name'])}", f"ORG:{_vc(card['org'])}", f"TEL;TYPE=CELL,VOICE:{phone}", f"NOTE:{_vc(note)}", f"URL:{scr._app_url()}"]
    try:
        with open(LOGO_PATH, "rb") as f:
            lines.append("PHOTO;ENCODING=b;TYPE=PNG:" + base64.b64encode(f.read()).decode())
    except OSError:
        pass
    return "\r\n".join(_fold(line) for line in lines + ["END:VCARD"]) + "\r\n"


def contact_page(card: dict, phone: str, client: Optional[dict], vcf_url: str) -> str:
    lang = loc.dialect(loc.key_of(client)) if client else "en"
    tr = lambda k, **kw: i18n.t(lang, k, **kw)
    body = tr("vcf.page_body", store=client["name"]) if client else tr("vcf.page_body_generic")
    shown = _pretty_phone(phone)
    return f"""<!DOCTYPE html><html lang="{lang[:2]}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>{_esc(tr('vcf.page_title', name=card['name']))}</title>
<style>body{{margin:0;background:#0b0b0c;color:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,Inter,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;padding:24px}}
.card{{max-width:420px;width:100%;background:#151517;border:1px solid #2a2a2e;border-radius:22px;padding:28px;text-align:center}}img{{width:84px;height:84px;border-radius:22px;margin:0 auto 16px;display:block}}
h1{{font-size:22px;margin:0 0 6px}}.num{{font-size:26px;font-weight:800;letter-spacing:.5px;color:#c9a962;margin:12px 0 4px}}.org{{color:#a1a1aa;font-size:14px}}p{{color:#d4d4d8;font-size:15px;line-height:1.55;margin:16px 0 22px}}
a.btn{{display:block;background:#c9a962;color:#111;text-decoration:none;font-weight:800;font-size:16px;border-radius:999px;padding:15px 20px}}.hint{{font-size:12.5px;color:#71717a;margin-top:14px}}</style></head>
<body><div class="card"><img src="/api/public/shop-contact/logo.png" alt="I'm On Social"><h1>{_esc(tr('vcf.page_title', name=card['name']))}</h1><div class="org">{_esc(card['org'])}</div><div class="num">{_esc(shown)}</div>
<p>{_esc(body)}</p><a class="btn" href="{vcf_url}" download="{_esc(card['name']).replace(' ', '_')}.vcf">{_esc(tr('vcf.save'))}</a><div class="hint">{_esc(tr('vcf.hint'))}</div></div></body></html>"""


def contact_sms(card: dict, client: dict, target: dict, sender: str, url: str) -> str:
    lang = loc.dialect(loc.key_of(client))
    return i18n.t(lang, "vcf.sms", name=(target.get("name") or "").split(" ")[0] or ("daar" if lang == "nl" else "there"), sender=sender, store=client["name"], card=card["name"], url=url)


async def send_contact_cards(db, client: dict, targets: list, me: dict) -> list:
    """Text the client's shop number as a saveable contact to each person: MMS with the .vcf attached where carriers take it (US/CA), a link everywhere."""
    from services.twilio_service import send_sms
    card = await contact_card_settings(db)
    frm = await from_number(db, client)
    page, vcf = contact_urls(await contact_token(db, client))
    country = loc.get(loc.key_of(client))["country"]
    sender = ((me.get("first_name") or me.get("name") or "Forest").split(" ")[0])
    out = []
    for t in targets:
        body = contact_sms(card, client, t, sender, page)
        r = await send_sms(t["phone"], body, media_urls=[vcf] if country in MMS_COUNTRIES else None, from_phone=frm or None)
        if not r.get("success") and country in MMS_COUNTRIES:
            r = await send_sms(t["phone"], body, from_phone=frm or None)
        ok = bool(r.get("success"))
        rec = {"sent_at": datetime.now(timezone.utc), "ok": ok, "error": None if ok else (r.get("error") or "Could not send"), "sid": r.get("sid"), "by": str(me.get("_id"))}
        await db.shop_targets.update_one({"_id": t["_id"]}, {"$set": {"contact_card": rec}})
        out.append({"id": str(t["_id"]), "name": t.get("name"), "phone": t.get("phone"), "ok": ok, "error": rec["error"]})
    return out


async def place_shop_call(db, call: dict) -> bool:
    if call.get("mode") == "text":
        return await tx.start_text_shop(db, call)
    if call.get("mode") == "email":
        return await ems.start_email_shop(db, call)
    from services.lead_call_engine import _twilio_client
    client = await db.shop_clients.find_one({"_id": _oid(call["client_id"])})
    tw = _twilio_client()
    frm = await from_number(db, client) if client else ""
    if not client or tw is None or not frm or not call.get("rep_phone"):
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "failed", "outcome": "not_configured", "fail_reason": "Calling is not set up (no caller number)", "updated_at": _now()}})
        return False
    sid, token = str(call["_id"]), call["token"]
    base = f"{scr._app_url()}/api/scripts/roleplay"
    now = _now()
    await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "dialing", "started_at": now, "last_attempt_at": now, "updated_at": now, "from_number": frm}, "$inc": {"attempts": 1}})
    try:
        tw_call = await asyncio.to_thread(
            tw.calls.create, to=call["rep_phone"], from_=frm, url=f"{base}/twiml/{sid}?t={token}", method="POST",
            status_callback=f"{base}/status/{sid}?t={token}", status_callback_event=["answered", "completed"], status_callback_method="POST",
            record=bool(client.get("record_calls", True)), recording_status_callback=f"{base}/recording/{sid}?t={token}", recording_status_callback_event=["completed"],
            timeout=25, time_limit=scr.CALL_TIME_LIMIT_S)
    except Exception as e:
        logger.warning(f"[MysteryShop] could not place call {sid}: {e}")
        await record_outcome(db, {**call, "attempts": call.get("attempts", 0) + 1}, "failed", "The call could not be placed")
        return False
    await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"call_sid": tw_call.sid, "call_status": "queued"}})
    return True


async def dial_now(db, call: dict) -> bool:
    """Immediate shops (Quick shop, Shop now): claim the row first so the 2-minute scheduler can never dial the same shop a second time."""
    claimed = await db.roleplay_sessions.find_one_and_update({"_id": call["_id"], "status": "scheduled"}, {"$set": {"status": "dialing", "updated_at": _now()}})
    if not claimed:
        return True  # the scheduler tick got there first and is already dialing it
    return await place_shop_call(db, call)


OUTCOME_LABEL = {"voicemail": "Went to voicemail", "no-answer": "No answer", "busy": "Line was busy", "failed": "The call could not be placed", "canceled": "The call was cancelled", "hung_up": "Hung up before the shop started",
                 "no_response": "Went to voicemail or wasn't ready", "postponed": "Asked us to call back later",
                 "carrier_declined": "Carrier spam filter declined the call", "declined": "Declined before it rang (carrier spam filter or the phone itself)",
                 "no_reply": f"No reply to the text in {tx.REPLY_WINDOW_MIN // 60} hours"}


async def postpone_call(db, call: dict, hours: int = 2):
    """Rep pressed 2 (bad time): automatic shops come back in a couple of hours, inside store hours, and it does not count as a try.
    Human-fired shops (Quick shop, Shop now, Call now, Try again) are never rescheduled: the shop is parked as 'asked us to call back' and the admin taps Try again."""
    client = await db.shop_clients.find_one({"_id": _oid(call["client_id"])}) or {}
    now = _now()
    history = {"at": now, "outcome": "postponed", "call_sid": call.get("call_sid")}
    if client.get("demo") or call.get("demo") or call.get("manual"):
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "unreachable", "outcome": "postponed", "fail_reason": OUTCOME_LABEL["postponed"], "ended_at": now, "updated_at": now}, "$push": {"attempt_history": history}})
        return
    when = now + timedelta(hours=hours)
    if client and not in_hours(client, when):
        when = next_slot(client, when, min_gap_minutes=0)
    await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "scheduled", "scheduled_for": when, "outcome": "postponed", "fail_reason": OUTCOME_LABEL["postponed"], "call_sid": None, "call_status": None, "turns": [], "updated_at": now},
                                                               "$inc": {"attempts": -1 if int(call.get("attempts") or 0) > 0 else 0},
                                                               "$push": {"attempt_history": history}})


async def record_outcome(db, call: dict, outcome: str, reason: Optional[str] = None):
    """A shop attempt that never became a conversation: automatic shops retry later inside business hours (or give up after max attempts).
    Human-fired shops (Quick shop, Shop now, course Call now, Try again) never auto-retry: they park as unreachable and the admin taps Try again."""
    client = await db.shop_clients.find_one({"_id": _oid(call["client_id"])}) or {}
    attempts = int(call.get("attempts") or 0)
    label = reason or OUTCOME_LABEL.get(outcome, outcome)
    if outcome in scr.SPAM_SIP.values() and scr.toll_free(call.get("from_number")):
        label += f", the shop number {call['from_number']} is toll-free and cell carriers flag those as spam, pick a local shop number"
    now = _now()
    history = {"at": now, "outcome": outcome, "call_sid": call.get("call_sid"), **({"sip_code": call["sip_code"]} if call.get("sip_code") else {})}
    hand_fired = bool(client.get("demo") or call.get("demo") or call.get("manual"))
    if attempts < int(call.get("max_attempts") or 3) and client and not hand_fired:
        when = next_slot(client, now, min_gap_minutes=random.randint(90, 240))
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "scheduled", "scheduled_for": when, "outcome": outcome, "fail_reason": f"{label}, trying again", "call_sid": None, "call_status": None, "turns": [], "updated_at": now},
                                                                   "$push": {"attempt_history": history}})
    else:
        tries = "" if hand_fired else f" ({attempts} {'try' if attempts == 1 else 'tries'})"
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "unreachable", "outcome": outcome, "fail_reason": f"{label}{tries}", "ended_at": now, "updated_at": now}, "$push": {"attempt_history": history}})
        if call.get("enrollment_id") and not hand_fired:
            from services import courses as cs
            e = await db.course_enrollments.find_one({"_id": ObjectId(call["enrollment_id"])}) if ObjectId.is_valid(str(call["enrollment_id"])) else None
            course = await db.courses.find_one({"_id": ObjectId(e["course_id"])}) if e else None
            rounds = int((e or {}).get("unreachable_rounds") or 0)
            if e and course and rounds < 3:
                await db.course_enrollments.update_one({"_id": e["_id"]}, {"$set": {"unreachable_rounds": rounds + 1, "updated_at": now}})
                await cs.schedule_next_shop(db, e, course, delay_minutes=24 * 60)


async def sweep_stuck_calls(db) -> int:
    """Lost Twilio callbacks: ask Twilio about anything still dialing after 2 min, give up after 10; finalize a 'live' call nobody has touched in 20 min."""
    now = _now()
    n = 0
    rows = await db.roleplay_sessions.find({"kind": "mystery_shop", "mode": "phone", "status": {"$in": ["dialing", "live"]}, "started_at": {"$lte": now - timedelta(minutes=2)}}).to_list(50)
    for s in rows:
        started = s["started_at"].replace(tzinfo=timezone.utc) if s["started_at"].tzinfo is None else s["started_at"]
        age = (now - started).total_seconds() / 60
        if s["status"] == "dialing":
            s = await scr.reconcile_dialing(db, s)
            if s.get("status") == "dialing" and age >= 10:
                await record_outcome(db, s, "no-answer")
                n += 1
        elif age >= scr.PHONE_MAX_MINUTES + 5:
            await scr.finalize_session(db, str(s["_id"]), "swept_stale")
            n += 1
    return n


async def run_due_calls(db, limit: int = 3) -> int:
    """Scheduler tick: dial shops whose time has come (inside the client's hours), a few at a time."""
    now = _now()
    try:
        await sweep_stuck_calls(db)
    except Exception as e:
        logger.warning(f"[MysteryShop] sweep failed: {e}")
    try:
        await tx.sweep(db)
    except Exception as e:
        logger.warning(f"[MysteryShop] text sweep failed: {e}")
    try:
        await ems.sweep(db)
    except Exception as e:
        logger.warning(f"[MysteryShop] email sweep failed: {e}")
    due = await db.roleplay_sessions.find({"kind": "mystery_shop", "status": "scheduled", "scheduled_for": {"$lte": now}}).sort("scheduled_for", 1).limit(limit * 3).to_list(limit * 3)
    placed = 0
    for call in due:
        if placed >= limit:
            break
        client = await db.shop_clients.find_one({"_id": _oid(call["client_id"])})
        if not client or not client.get("active", True):
            await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "canceled", "fail_reason": "Client paused", "updated_at": now}})
            continue
        if not call.get("manual") and not client.get("demo") and not in_hours(client, now):
            await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"scheduled_for": next_slot(client, now, min_gap_minutes=0), "updated_at": now}})
            continue
        busy = await db.roleplay_sessions.find_one({"kind": "mystery_shop", "target_id": call["target_id"], "status": {"$in": ["dialing", "live", "ending", "grading"]}, **mode_q(call.get("mode"))}, {"_id": 1})
        if busy:
            await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"scheduled_for": now + timedelta(minutes=45), "updated_at": now}})
            continue
        claimed = await db.roleplay_sessions.find_one_and_update({"_id": call["_id"], "status": "scheduled"}, {"$set": {"status": "dialing", "updated_at": now}})
        if claimed and await place_shop_call(db, claimed):
            placed += 1
    return placed


async def plan_active_clients(db) -> int:
    """Daily: make sure every active client's current month is fully scheduled."""
    n = 0
    async for client in db.shop_clients.find({"active": {"$ne": False}}):
        try:
            made = await plan_month(db, client)
            n += sum(made.values())
        except Exception as e:
            logger.warning(f"[MysteryShop] planning failed for {client.get('name')}: {e}")
    return n


# ---------------------------------------------------------------- grading hook (called from scripts.grade_session)
async def scorecard_for(db, session: dict) -> Optional[dict]:
    client = await db.shop_clients.find_one({"_id": _oid(session["client_id"])}) or {}
    dept = session.get("department") or "sales"
    cid = (client.get("scorecards") or {}).get(dept)
    if cid and ObjectId.is_valid(str(cid)):
        card = await db.scorecards.find_one({"_id": ObjectId(str(cid)), "active": {"$ne": False}})
        if card:
            return card
    return template_card(dept, loc.key_of(client))


def template_card(dept: str, locale: Optional[str] = None) -> Optional[dict]:
    """The department's built-in scorecard (from its industry pack), in the client's language, so every course taker and every shop is graded the same way."""
    d = ind.dept(dept)
    if d.get("template"):
        body = sc.template_body(d["template"], loc.language(locale))
        if not body:
            return None
        return {"_id": None, "name": body["name"], "department": body["department"], "criteria": sc.normalize_criteria(body["criteria"]), "alert_on_critical": False}
    card = d.get("scorecard") or {}
    if not card.get("criteria"):
        return None
    return {"_id": None, "name": card.get("name") or f"{d['label']} Call", "department": d["label"], "criteria": sc.normalize_criteria(card["criteria"]), "alert_on_critical": False}


# ---------------------------------------------------------------- report
def _pct(vals: list) -> Optional[int]:
    vals = [v for v in vals if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals)) if vals else None


def _call_row(c: dict, ev: Optional[dict]) -> dict:
    """A shop as the report and the person page show it: call + its evaluation (summary, misses, coaching, transcript)."""
    ev = ev or {}
    return {**serialize_call(c), "summary": ev.get("summary"), "critical_misses": sc.miss_labels(ev), "coaching": ev.get("coaching") or [],
            "wins": ev.get("wins") or [], "adherence": ev.get("adherence") or {}, "results": ev.get("results") or [], "transcript": ev.get("transcript") or scr.transcript_text(c),
            "customer_sentiment": ev.get("customer_sentiment")}


def _snippet(transcript: str, lines: int = 4, max_chars: int = 320) -> str:
    """The opening exchange of a call (how the phone was answered decides most of the score)."""
    rows = [r.strip() for r in (transcript or "").splitlines() if r.strip()]
    out = " ".join(rows[:lines])
    return out if len(out) <= max_chars else out[:max_chars].rsplit(" ", 1)[0] + "..."


async def person_history(db, client: dict, target_id: str, months: int = 6) -> Optional[dict]:
    """Everything a GM wants when tapping a name: every shop across months, trend, departments, opening snippets."""
    if not ObjectId.is_valid(str(target_id)):
        return None
    cid = str(client["_id"])
    target = await db.shop_targets.find_one({"_id": ObjectId(str(target_id)), "client_id": cid})
    if not target:
        return None
    tz = _tz(client)
    calls = await db.roleplay_sessions.find({"kind": "mystery_shop", "client_id": cid, "target_id": str(target_id), "status": {"$ne": "canceled"}}).sort("scheduled_for", -1).to_list(120)
    done = [c for c in calls if c.get("status") == "completed"]
    ev_ids = [ObjectId(c["evaluation_id"]) for c in done if c.get("evaluation_id") and ObjectId.is_valid(str(c["evaluation_id"]))]
    evals = {str(e["_id"]): e for e in await db.call_evaluations.find({"_id": {"$in": ev_ids}}).to_list(200)} if ev_ids else {}
    # month buckets, newest last, always the last `months` months even when empty
    now_local = _now().astimezone(tz)
    buckets = []
    for i in range(months - 1, -1, -1):
        y, m = now_local.year, now_local.month - i
        while m <= 0:
            y, m = y - 1, m + 12
        buckets.append({"month": f"{y:04d}-{m:02d}", "label": datetime(y, m, 1).strftime("%b %Y"), "shops": 0, "unreachable": 0, "scores": [], "by_department": {}})
    idx = {b["month"]: b for b in buckets}
    for c in calls:
        when = (c.get("ended_at") or c.get("scheduled_for"))
        if not when:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        b = idx.get(when.astimezone(tz).strftime("%Y-%m"))
        if not b:
            continue
        dept = c.get("department") or "sales"
        if c.get("status") == "completed":
            b["shops"] += 1
            b["scores"].append(c.get("score_pct"))
            bd = b["by_department"].setdefault(dept, {"label": ind.dept_label(dept), "shops": 0, "scores": []})
            bd["shops"] += 1
            bd["scores"].append(c.get("score_pct"))
        elif c.get("status") == "unreachable":
            b["unreachable"] += 1
    trend = []
    for b in buckets:
        trend.append({"month": b["month"], "label": b["label"], "shops": b["shops"], "unreachable": b["unreachable"], "avg_score": _pct(b["scores"]),
                      "by_department": {d: {"label": v["label"], "shops": v["shops"], "avg_score": _pct(v["scores"])} for d, v in b["by_department"].items()}})
    scored = [t for t in trend if t["avg_score"] is not None]
    delta = (scored[-1]["avg_score"] - scored[-2]["avg_score"]) if len(scored) >= 2 else None
    depts: dict = {}
    for c in done:
        d = c.get("department") or "sales"
        depts.setdefault(d, {"label": ind.dept_label(d), "shops": 0, "scores": [], "critical_misses": 0})
        depts[d]["shops"] += 1
        depts[d]["scores"].append(c.get("score_pct"))
        depts[d]["critical_misses"] += len((evals.get(str(c.get("evaluation_id"))) or {}).get("critical_misses") or [])
    shops = []
    for c in calls[:40]:
        if c.get("status") not in ("completed", "unreachable"):
            continue
        ev = evals.get(str(c.get("evaluation_id"))) if c.get("evaluation_id") else None
        row = _call_row(c, ev)
        row["department_label"] = ind.dept_label(c.get("department") or "sales")
        row["snippet"] = _snippet(row.get("transcript") or "") if c.get("status") == "completed" else ""
        row["month"] = ((c.get("ended_at") or c.get("scheduled_for")).astimezone(tz).strftime("%Y-%m")) if (c.get("ended_at") or c.get("scheduled_for")) else None
        shops.append(row)
    all_scores = [c.get("score_pct") for c in done]
    # the line to compare against: every completed shop on this account in the same window, overall + per department + per month
    window_start = datetime(int(buckets[0]["month"][:4]), int(buckets[0]["month"][5:]), 1, tzinfo=tz).astimezone(timezone.utc)
    store_done = await db.roleplay_sessions.find({"kind": "mystery_shop", "client_id": cid, "status": "completed", "$or": [{"ended_at": {"$gte": window_start}}, {"scheduled_for": {"$gte": window_start}}]},
                                                 {"score_pct": 1, "department": 1, "ended_at": 1, "scheduled_for": 1, "target_id": 1}).to_list(2000)
    store_by_dept: dict = {}
    store_by_month: dict = {}
    for c in store_done:
        d = c.get("department") or "sales"
        store_by_dept.setdefault(d, []).append(c.get("score_pct"))
        when = c.get("ended_at") or c.get("scheduled_for")
        if when:
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            store_by_month.setdefault(when.astimezone(tz).strftime("%Y-%m"), []).append(c.get("score_pct"))
    for t in trend:
        t["store_avg_score"] = _pct(store_by_month.get(t["month"], []))
    store_avg = _pct([c.get("score_pct") for c in store_done])
    store = {"avg_score": store_avg, "shops": len(store_done), "people": len({c.get("target_id") for c in store_done}),
             "by_department": {d: {"label": ind.dept_label(d), "avg_score": _pct(v), "shops": len(v)} for d, v in store_by_dept.items()}}
    crit_total = sum(len((evals.get(str(c.get("evaluation_id"))) or {}).get("critical_misses") or []) for c in done)
    coaching: dict = {}
    for c in done:
        for tip in ((evals.get(str(c.get("evaluation_id"))) or {}).get("coaching") or [])[:3]:
            key = no_em_dash(str(tip)).strip().rstrip(".")
            coaching[key] = coaching.get(key, 0) + 1
    avg = _pct(all_scores)
    vs_store = (avg - store_avg) if (avg is not None and store_avg is not None) else None
    vs_dept = {}
    for d, v in depts.items():
        mine, line = _pct(v["scores"]), _pct(store_by_dept.get(d, []))
        if mine is not None and line is not None:
            vs_dept[d] = mine - line
    return {"person": {"target_id": str(target["_id"]), "name": target.get("name"), "title": target.get("title") or "", "department": target.get("department"), "department_label": ind.dept_label(target.get("department") or "sales"),
                       "phone_last4": (target.get("phone") or "")[-4:], "active": target.get("active", True)},
            "summary": {"shops": len(done), "unreachable": len([c for c in calls if c.get("status") == "unreachable"]), "avg_score": avg, "best": max([s for s in all_scores if s is not None], default=None),
                        "worst": min([s for s in all_scores if s is not None], default=None), "critical_misses": crit_total, "trend_delta": delta,
                        "needs_training": bool(done and ((avg is not None and avg < 70) or crit_total >= 2)), "first_shop": (done[-1].get("ended_at") or done[-1].get("scheduled_for")).isoformat() if done else None},
            "departments": {d: {"label": v["label"], "shops": v["shops"], "avg_score": _pct(v["scores"]), "critical_misses": v["critical_misses"]} for d, v in depts.items()},
            "trend": trend, "shops": shops, "coaching_themes": [{"text": k, "count": v} for k, v in sorted(coaching.items(), key=lambda kv: -kv[1])[:5]],
            "store": store, "vs_store": vs_store, "vs_department": vs_dept,
            "client": {"id": cid, "name": client.get("name")}}


def leaderboard(people: list, prev_scores: dict, prev_label: str) -> list:
    """Rank one department's people by average score (ties: more shops, then name). prev_scores = {target_id: [last month's scores]}."""
    ranked = sorted([r for r in people if r.get("completed") and r.get("avg_score") is not None], key=lambda r: (-r["avg_score"], -r["completed"], r.get("name") or ""))
    board = []
    for i, r in enumerate(ranked):
        pv = _pct(prev_scores.get(r["target_id"], []))
        board.append({"rank": i + 1, "key": r["key"], "target_id": r["target_id"], "name": r["name"], "title": r.get("title") or "", "avg_score": r["avg_score"], "completed": r["completed"],
                      "best": r.get("best"), "critical_misses": r.get("critical_misses", 0), "prev_avg": pv, "delta": (r["avg_score"] - pv) if pv is not None else None, "badges": []})
    if not board:
        return board
    top = max(board, key=lambda b: (b["best"] if b["best"] is not None else -1))
    if top["best"] is not None:
        top["badges"].append({"key": "top_score", "label": "Top score", "detail": f"{top['best']}% on one call"})
    climbers = [b for b in board if b["delta"] is not None and b["delta"] > 0]
    if climbers:
        mi = max(climbers, key=lambda b: b["delta"])
        mi["badges"].append({"key": "most_improved", "label": "Most improved", "detail": f"+{mi['delta']} vs {prev_label}"})
    busiest = max(board, key=lambda b: b["completed"])
    if busiest["completed"] > 1 and sum(1 for b in board if b["completed"] == busiest["completed"]) == 1:
        busiest["badges"].append({"key": "most_shops", "label": "Most shops", "detail": f"{busiest['completed']} shops"})
    return board


async def build_report(db, client: dict, month: Optional[str] = None) -> dict:
    tz = _tz(client)
    start, end = month_bounds(month, tz)
    cid = str(client["_id"])
    calls = await db.roleplay_sessions.find({"kind": "mystery_shop", "client_id": cid, "scheduled_for": {"$gte": start, "$lt": end}, "status": {"$ne": "canceled"}}).sort("scheduled_for", 1).to_list(500)
    done = [c for c in calls if c.get("status") == "completed"]
    ev_ids = [ObjectId(c["evaluation_id"]) for c in done if c.get("evaluation_id") and ObjectId.is_valid(str(c["evaluation_id"]))]
    evals = {str(e["_id"]): e for e in await db.call_evaluations.find({"_id": {"$in": ev_ids}}).to_list(500)} if ev_ids else {}
    targets = {str(t["_id"]): t for t in await db.shop_targets.find({"client_id": cid}).to_list(500)}
    # one row per person PER DEPARTMENT: quick shops reuse the same target for a sales call and a service call, and the
    # target's department is whatever the LAST shop set it to, so the call's own department is the truth
    people = {}
    for c in calls:
        dept = c.get("department") or (targets.get(c["target_id"]) or {}).get("department") or "sales"
        p = people.setdefault((c["target_id"], dept), {"key": f"{c['target_id']}:{dept}", "target_id": c["target_id"], "name": c.get("rep_name"), "department": dept, "department_label": ind.dept_label(dept),
                                                        "shops": 0, "completed": 0, "unreachable": 0, "scores": [], "adherence": [], "critical_misses": 0, "last_shop": None, "coaching": []})
        p["shops"] += 1
        if c.get("status") == "completed":
            p["completed"] += 1
            p["scores"].append(c.get("score_pct"))
            p["adherence"].append(c.get("adherence_pct"))
            ev = evals.get(str(c.get("evaluation_id")))
            if ev:
                p["critical_misses"] += len(ev.get("critical_misses") or [])
                p["coaching"] += (ev.get("coaching") or [])[:2]
            p["last_shop"] = (c.get("ended_at") or c.get("scheduled_for"))
        elif c.get("status") == "unreachable":
            p["unreachable"] += 1
    rows = []
    for p in people.values():
        avg = _pct(p["scores"])
        rows.append({**p, "avg_score": avg, "avg_adherence": _pct(p["adherence"]), "best": max([s for s in p["scores"] if s is not None], default=None), "worst": min([s for s in p["scores"] if s is not None], default=None),
                     "needs_training": bool(p["completed"] and ((avg is not None and avg < 70) or p["critical_misses"] >= 2)), "last_shop": p["last_shop"].isoformat() if p["last_shop"] else None,
                     "title": (targets.get(p["target_id"]) or {}).get("title", ""), "coaching": p["coaching"][:3]})
        rows[-1].pop("scores"); rows[-1].pop("adherence")
    rows.sort(key=lambda r: (r["avg_score"] is None, -(r["avg_score"] or 0)))
    # what the store misses: pass rate per criterion text (N/A excluded), kept PER DEPARTMENT so one service shop's misses
    # never sit at the top of a list dominated by sales shops
    ev_dept = {str(c.get("evaluation_id")): (c.get("department") or "sales") for c in done if c.get("evaluation_id")}
    crit = {}
    for eid, ev in evals.items():
        dept = ev_dept.get(eid, "sales")
        for r in ev.get("results") or []:
            if r.get("passed") is None:
                continue
            k = r.get("text") or r.get("criterion_id")
            d = crit.setdefault((dept, k), {"text": k, "critical": bool(r.get("critical")), "passed": 0, "total": 0, "department": dept, "department_label": ind.dept_label(dept)})
            d["total"] += 1
            d["passed"] += 1 if r.get("passed") else 0
    criteria = sorted([{**d, "pass_pct": round(100 * d["passed"] / d["total"])} for d in crit.values() if d["total"]], key=lambda d: (d["pass_pct"], -d["total"]))
    scores = [c.get("score_pct") for c in done]
    by_dept = {}
    per, text_per = plan_per_month(client), plan_text_per_month(client)
    depts = list(dict.fromkeys(ind.dept_keys(ind.key_of(client)) + [c.get("department") for c in calls if c.get("department")]))
    for d in depts:
        dc = [c for c in done if c.get("department") == d]
        if not per.get(d) and not text_per.get(d) and not dc and not any(c.get("department") == d for c in calls):
            continue
        by_dept[d] = {"label": ind.dept_label(d), "planned": int(per.get(d) or 0) + int(text_per.get(d) or 0), "planned_calls": int(per.get(d) or 0), "planned_texts": int(text_per.get(d) or 0),
                      "text_completed": len([c for c in dc if c.get("mode") == "text"]), "scheduled": len([c for c in calls if c.get("department") == d and c.get("status") in CALL_STATUSES_OPEN]),
                      "completed": len(dc), "unreachable": len([c for c in calls if c.get("department") == d and c.get("status") == "unreachable"]), "avg_score": _pct([c.get("score_pct") for c in dc]),
                      "people": len({c["target_id"] for c in dc}), "criteria": [cr for cr in criteria if cr["department"] == d]}
    call_rows = []
    for c in sorted(calls, key=lambda x: x.get("ended_at") or x.get("scheduled_for") or _now(), reverse=True):
        call_rows.append(_call_row(c, evals.get(str(c.get("evaluation_id"))) if c.get("evaluation_id") else None))
    # coaching themes per department: a service manager should never get sales tips in their section
    themes_by_dept: dict = {}
    for eid, ev in evals.items():
        dept = ev_dept.get(eid, "sales")
        for tip in (ev.get("coaching") or [])[:3]:
            key = no_em_dash(str(tip)).strip().rstrip(".")
            themes_by_dept.setdefault(dept, {})[key] = themes_by_dept.get(dept, {}).get(key, 0) + 1
    for d, counts in themes_by_dept.items():
        if d in by_dept:
            by_dept[d]["coaching_themes"] = [{"text": k, "count": v} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])[:6]]
    themes: dict = {}
    for counts in themes_by_dept.values():
        for k, v in counts.items():
            themes[k] = themes.get(k, 0) + v
    # leaderboard PER DEPARTMENT (a parts counterperson is never ranked against a salesperson): average first, then volume;
    # badges for the best single shop, the biggest climb since last month and the most shops
    prev_month = (start.astimezone(tz) - timedelta(days=1)).strftime("%Y-%m")
    p_start, p_end = month_bounds(prev_month, tz)
    prev_label = p_start.astimezone(tz).strftime("%b")
    prev_scores: dict = {}
    for c in await db.roleplay_sessions.find({"kind": "mystery_shop", "client_id": cid, "status": "completed", "scheduled_for": {"$gte": p_start, "$lt": p_end}}, {"target_id": 1, "department": 1, "score_pct": 1}).to_list(500):
        prev_scores.setdefault((c["target_id"], c.get("department") or "sales"), []).append(c.get("score_pct"))
    for d, dv in by_dept.items():
        dv["leaderboard"] = leaderboard([r for r in rows if r["department"] == d], {k[0]: v for k, v in prev_scores.items() if k[1] == d}, prev_label)
    lang = loc.dialect(loc.key_of(client))
    label = i18n.month_label(start.astimezone(tz), lang)
    prev_label = i18n.month_label(p_start.astimezone(tz), lang, short=True)
    if lang != "en":
        for d, dv in by_dept.items():
            dv["label"] = ind.dept_label_for(d, loc.key_of(client), ind.key_of(client))
            for r in dv.get("leaderboard") or []:
                for b in r["badges"]:
                    b["label"] = i18n.t(lang, f"badge.{b['key']}")
                    b["detail"] = i18n.t(lang, f"badge.{b['key']}.detail", v=(r.get("best") if b["key"] == "top_score" else r.get("delta")), prev=prev_label, n=r.get("completed"))
        for r in rows:
            r["department_label"] = ind.dept_label_for(r["department"], loc.key_of(client), ind.key_of(client))
    industry = ind.key_of(client)
    pack_t = ind.translated(industry, loc.key_of(client))
    return {"client": {"id": cid, "name": client.get("name"), "brand": client.get("brand", ""), "city": client.get("city", ""), "state": client.get("state", ""), "contact_name": client.get("contact_name", ""),
                       "industry": ind.key_of(client), "industry_label": pack_t["label"], "customer_noun": pack_t["customer"], "business_noun": pack_t["business"], "locale": loc.key_of(client), "language": lang},
            "month": start.astimezone(tz).strftime("%Y-%m"), "month_label": label, "prev_month_label": prev_label, "language": lang, "generated_at": _now().isoformat(),
            "summary": {"completed": len(done), "planned": sum(v["planned"] for v in by_dept.values()), "scheduled": len([c for c in calls if c.get("status") in CALL_STATUSES_OPEN]),
                        "unreachable": len([c for c in calls if c.get("status") == "unreachable"]), "avg_score": _pct(scores), "avg_adherence": _pct([c.get("adherence_pct") for c in done]),
                        "people_shopped": len({r["target_id"] for r in rows if r["completed"]}), "needs_training": len([r for r in rows if r["needs_training"]]),
                        "text_shops": len([c for c in done if c.get("mode") == "text"]), "text_no_reply": len([c for c in done if c.get("mode") == "text" and c.get("outcome") == "no_reply"]),
                        "avg_first_reply_s": _pct([tx.stats(c)["first_reply_s"] for c in done if c.get("mode") == "text" and tx.stats(c)["first_reply_s"] is not None]),
                        "email_shops": len([c for c in done if c.get("mode") == "email"]), "email_no_reply": len([c for c in done if c.get("mode") == "email" and c.get("outcome") == "no_reply"]),
                        "avg_first_email_reply_s": _pct([tx.stats(c)["first_reply_s"] for c in done if c.get("mode") == "email" and tx.stats(c)["first_reply_s"] is not None])},
            "by_department": by_dept, "people": rows, "criteria": criteria, "coaching_themes": [{"text": k, "count": v} for k, v in sorted(themes.items(), key=lambda kv: -kv[1])[:6]], "calls": call_rows}


def report_pdf(report: dict) -> bytes:
    from fpdf import FPDF
    GOLD, INK, MUTED, RED, GREEN = (201, 169, 98), (20, 20, 20), (110, 110, 110), (220, 60, 50), (40, 160, 90)
    pdf = FPDF(format="letter")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(16, 16, 16)
    pdf.add_page()

    def txt(s: str) -> str:
        return (s or "").encode("latin-1", "replace").decode("latin-1")

    def h(s, size=16, color=INK, gap=2):
        pdf.set_font("Helvetica", "B", size); pdf.set_text_color(*color); pdf.cell(0, size * 0.5, txt(s), new_x="LMARGIN", new_y="NEXT"); pdf.ln(gap)

    def p(s, size=10, color=INK, style=""):
        pdf.set_font("Helvetica", style, size); pdf.set_text_color(*color); pdf.multi_cell(0, size * 0.5, txt(s), new_x="LMARGIN", new_y="NEXT")

    c, s = report["client"], report["summary"]
    lang = report.get("language") or "en"
    tr = lambda k, **kw: i18n.t(lang, k, **kw)
    pdf.set_font("Helvetica", "B", 9); pdf.set_text_color(*GOLD); pdf.cell(0, 5, txt(tr("pdf.kicker")), new_x="LMARGIN", new_y="NEXT")
    h(f"{c['name']}", 20)
    p(f"{report['month_label']}  |  {c.get('brand') or ''}  {c.get('city') or ''} {c.get('state') or ''}".strip(), 10, MUTED)
    pdf.ln(3)
    pdf.set_fill_color(247, 243, 232)
    boxes = [(tr("pdf.completed"), tr("pdf.of", a=s['completed'], b=s['planned']) if s.get("planned") else str(s['completed'])), (tr("pdf.avg"), f"{s['avg_score']}%" if s['avg_score'] is not None else tr("pdf.na")),
             (tr("pdf.people"), str(s['people_shopped'])), (tr("pdf.need"), str(s['needs_training']))]
    w = (pdf.w - 32) / 4
    y = pdf.get_y()
    for i, (lab, val) in enumerate(boxes):
        x = 16 + i * w
        pdf.set_xy(x, y); pdf.set_fill_color(247, 243, 232); pdf.rect(x + 1, y, w - 2, 18, "F")
        pdf.set_xy(x + 3, y + 2); pdf.set_font("Helvetica", "B", 14); pdf.set_text_color(*INK); pdf.cell(w - 6, 8, txt(val))
        pdf.set_xy(x + 3, y + 10); pdf.set_font("Helvetica", "", 8); pdf.set_text_color(*MUTED); pdf.cell(w - 6, 6, txt(lab.upper()))
    pdf.set_y(y + 24)

    depts = [(k, v) for k, v in (report.get("by_department") or {}).items() if v.get("planned") or v.get("completed") or v.get("scheduled") or v.get("unreachable")]
    if depts:
        # one card per department (sales, service, parts, collision... whatever the industry pack + this month's shops contain)
        per_row = 2 if len(depts) <= 2 else 3
        dw = (pdf.w - 32) / per_row
        for i in range(0, len(depts), per_row):
            y = pdf.get_y()
            for j, (dk, dv) in enumerate(depts[i:i + per_row]):
                x = 16 + j * dw
                pdf.set_fill_color(247, 243, 232); pdf.rect(x + 1, y, dw - 2, 20, "F")
                pdf.set_xy(x + 3, y + 1.5); pdf.set_font("Helvetica", "B", 8.5); pdf.set_text_color(*GOLD); pdf.cell(dw - 6, 5, txt((dv.get("label") or ind.dept_label(dk)).upper()))
                parts = [f"{dv['completed']} done" + (f" of {dv['planned']}" if dv.get("planned") else "")]
                if dv.get("scheduled"):
                    parts.append(f"{dv['scheduled']} coming")
                if dv.get("unreachable"):
                    parts.append(f"{dv['unreachable']} unreachable")
                pdf.set_xy(x + 3, y + 7); pdf.set_font("Helvetica", "", 9); pdf.set_text_color(*INK); pdf.cell(dw - 6, 5, txt("  |  ".join(parts)))
                avg = dv.get("avg_score")
                pdf.set_xy(x + 3, y + 13); pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(*(MUTED if avg is None else RED if avg < 70 else GOLD if avg < 85 else GREEN)); pdf.cell(dw - 6, 5, txt(tr("pdf.avg_short", v=avg) if avg is not None else tr("pdf.no_scores")))
            pdf.set_y(y + 24)

    boards = [(dk, dv) for dk, dv in (report.get("by_department") or {}).items() if dv.get("leaderboard")]
    if boards:
        # one ranked table per department: the recognition piece of the report
        prev = (report.get("prev_month_label") or "last month").upper()
        for dk, dv in boards:
            h(tr("pdf.leaderboard", dept=dv.get('label') or ind.dept_label(dk)), 13)
            pdf.set_font("Helvetica", "B", 9); pdf.set_text_color(*MUTED)
            for lab, cw in (("#", 8), (tr("pdf.col.name"), 56), (tr("pdf.col.shops"), 16), (tr("pdf.col.avg"), 16), (tr("pdf.col.best"), 16), (tr("pdf.col.vs", prev=prev), 22), (tr("pdf.col.recognition"), 48)):
                pdf.cell(cw, 6, txt(lab))
            pdf.ln(6)
            for r in dv["leaderboard"]:
                pdf.set_font("Helvetica", "B" if r["rank"] <= 3 else "", 10); pdf.set_text_color(*(GOLD if r["rank"] == 1 else INK))
                pdf.cell(8, 6, str(r["rank"])); pdf.cell(56, 6, txt((r["name"] or "")[:30])); pdf.cell(16, 6, str(r["completed"]))
                pdf.cell(16, 6, f"{r['avg_score']}%"); pdf.cell(16, 6, f"{r['best']}%" if r.get("best") is not None else "-")
                d = r.get("delta")
                pdf.set_text_color(*(GREEN if (d or 0) > 0 else RED if (d or 0) < 0 else MUTED)); pdf.cell(22, 6, f"{'+' if d > 0 else ''}{d}" if d is not None else tr("pdf.new"))
                pdf.set_text_color(*GOLD); pdf.set_font("Helvetica", "B", 8.5); pdf.cell(48, 6, txt(", ".join(b["label"] for b in r["badges"])), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

    h(tr("pdf.who"), 13)
    pdf.set_font("Helvetica", "B", 9); pdf.set_text_color(*MUTED)
    for lab, cw in ((tr("pdf.col.name"), 60), (tr("pdf.col.dept"), 24), (tr("pdf.col.shops"), 18), (tr("pdf.col.avg"), 18), (tr("pdf.col.best"), 18), (tr("pdf.col.crit"), 26), (tr("pdf.col.status"), 30)):
        pdf.cell(cw, 6, lab)
    pdf.ln(6)
    for r in report["people"]:
        pdf.set_font("Helvetica", "", 10); pdf.set_text_color(*INK)
        pdf.cell(60, 6, txt(r["name"][:32])); pdf.cell(24, 6, txt((r.get("department_label") or ind.dept_label(r["department"]))[:14])); pdf.cell(18, 6, str(r["completed"]))
        pdf.cell(18, 6, f"{r['avg_score']}%" if r["avg_score"] is not None else "-"); pdf.cell(18, 6, f"{r['best']}%" if r["best"] is not None else "-"); pdf.cell(26, 6, str(r["critical_misses"]))
        pdf.set_text_color(*(RED if r["needs_training"] else (GREEN if r["completed"] else MUTED))); pdf.set_font("Helvetica", "B", 9)
        pdf.cell(30, 6, txt(tr("pdf.status.needs") if r["needs_training"] else (tr("pdf.status.ok") if r["completed"] else (tr("pdf.status.unreachable") if r["unreachable"] else tr("pdf.status.scheduled")))), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if report["criteria"]:
        # one section per department so a single service shop's misses are not read as store-wide sales problems
        groups = [(dk, dv) for dk, dv in (report.get("by_department") or {}).items() if dv.get("criteria")] or [("all", {"label": "the whole store", "completed": report["summary"]["completed"], "criteria": report["criteria"]})]
        for dk, dv in groups:
            n = dv.get("completed") or 0
            h(tr("pdf.misses", dept=dv.get('label') or ind.dept_label(dk)) + (f"  ({tr('pdf.shops_n' if n == 1 else 'pdf.shops_np', n=n)})" if n else ""), 13)
            for cr in dv["criteria"][:8]:
                pdf.set_font("Helvetica", "", 10); pdf.set_text_color(*INK)
                bar_w = 60; x = pdf.get_x(); y = pdf.get_y()
                pdf.set_fill_color(235, 235, 235); pdf.rect(x, y + 1.5, bar_w, 4, "F")
                pdf.set_fill_color(*(RED if cr["pass_pct"] < 60 else GOLD if cr["pass_pct"] < 85 else GREEN)); pdf.rect(x, y + 1.5, bar_w * cr["pass_pct"] / 100, 4, "F")
                pdf.set_xy(x + bar_w + 3, y); pdf.set_font("Helvetica", "B", 9); pdf.cell(12, 7, f"{cr['pass_pct']}%")
                pdf.set_font("Helvetica", "", 9); pdf.multi_cell(0, 7, txt(cr["text"] + (f"  {tr('pdf.critical')}" if cr["critical"] else "") + (f"  -  {tr('pdf.x_of_y', a=cr['passed'], b=cr['total'])}" if cr.get("total") else "")), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

    theme_groups = [(dk, dv) for dk, dv in (report.get("by_department") or {}).items() if dv.get("coaching_themes")]
    if theme_groups:
        # one block per department so the service manager's section only carries service tips
        for dk, dv in theme_groups:
            h(tr("pdf.themes_dept", dept=dv.get('label') or ind.dept_label(dk)), 13)
            for t in dv["coaching_themes"]:
                p(f"-  {t['text']}" + (f"  (x{t['count']})" if t.get("count", 1) > 1 else ""), 10)
            pdf.ln(3)
    elif report["coaching_themes"]:
        h(tr("pdf.themes"), 13)
        for t in report["coaching_themes"]:
            p(f"-  {t['text']}", 10)
        pdf.ln(3)

    done = [cr for cr in report["calls"] if cr["status"] == "completed"]
    if done:
        pdf.add_page()
        h(tr("pdf.every"), 13)
        for cr in done:
            when = datetime.fromisoformat(cr["ended_at"]) if cr.get("ended_at") else None
            pdf.set_font("Helvetica", "B", 11); pdf.set_text_color(*INK)
            head = f"{cr['target_name']}  |  {ind.dept_label_for(cr.get('department') or 'sales', report['client'].get('locale'))}  |  {cr['script_title']}"
            pdf.cell(0, 6, txt(head + (f"  |  {cr['score_pct']}%" if cr["score_pct"] is not None else "")), new_x="LMARGIN", new_y="NEXT")
            p((when.strftime("%b %d, %I:%M %p UTC") if when else "") + (f"  |  {'Beller' if lang == 'nl' else 'Shopper'}: {cr['persona_name']}" if cr.get("persona_name") else ""), 8.5, MUTED)
            if cr.get("summary"):
                p(cr["summary"], 9.5)
            if cr.get("critical_misses"):
                p(tr("pdf.crit_misses") + "; ".join(str(m) for m in cr["critical_misses"]), 9.5, RED, "B")
            for tip in (cr.get("coaching") or [])[:3]:
                p(f"-  {tip}", 9.5)
            pdf.ln(2)
    pdf.set_y(-14); pdf.set_font("Helvetica", "", 8); pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, txt(f"{'Opgesteld door' if lang == 'nl' else 'Prepared by'} I'm On Social  |  imonsocial.com  |  {report['generated_at'][:10]}"), align="C")
    return bytes(pdf.output())


# ---------------------------------------------------------------- proposals + Stripe invoice
def _stripe():
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"
    return stripe


def serialize_proposal(p: dict) -> dict:
    return {"id": str(p["_id"]), "client_id": p.get("client_id"), "token": p.get("token"), "status": p.get("status"), "terms": p.get("terms") or {}, "client_name": p.get("client_name"),
            "contact_name": p.get("contact_name"), "contact_email": p.get("contact_email"), "created_at": p["created_at"].isoformat() if p.get("created_at") else None,
            "sent_at": p["sent_at"].isoformat() if p.get("sent_at") else None, "viewed_at": p["viewed_at"].isoformat() if p.get("viewed_at") else None,
            "signed_at": p["signed_at"].isoformat() if p.get("signed_at") else None, "signer": {k: v for k, v in (p.get("signer") or {}).items() if k != "ip"},
            "invoice": {k: v for k, v in (p.get("invoice") or {}).items()}, "sender_name": p.get("sender_name")}


def proposal_text(p: dict, locale: Optional[str] = None) -> list:
    t = p.get("terms") or {}
    lang = loc.dialect(locale)
    en = loc.language(locale) == "en"
    price = float(t.get("price_monthly") or 0)
    sym = loc.get(locale)["symbol"]
    price_s = f"{sym}{price:,.0f}" if en else f"{sym} {price:,.0f}".replace(",", ".")
    per = terms_per_month(t)
    term = int(t.get("term_months") or 3)
    tr = lambda k, **kw: i18n.t(lang, k, **kw)
    per_text = per_month_text_for(per, locale, " and " if en else " en ")
    text_per = {k: int(v or 0) for k, v in ((t.get("text_per_month") or {}) if isinstance(t.get("text_per_month"), dict) else {}).items() if int(v or 0) > 0}
    what = tr("prop.what.body", client=p.get("client_name"), per=per_text) + (tr("prop.what.text", per=per_month_text_for(text_per, locale, " and " if en else " en ")) if text_per else "")
    return [
        (tr("prop.what.title"), what),
        (tr("prop.report.title"), tr("prop.report.body")),
        (tr("prop.invest.title"), tr("prop.invest.body", price=price_s, term=term)),
        (tr("prop.part.title"), tr("prop.part.body")),
        (tr("prop.cancel.title"), tr("prop.cancel.body", term=term)),
        (tr("prop.agree.title"), tr("prop.agree.body")),
    ] + ([(tr("prop.notes.title"), t["notes"])] if t.get("notes") else [])


async def create_invoice_for(db, proposal: dict) -> dict:
    """First month's invoice, emailed by Stripe with a hosted payment page."""
    stripe = _stripe()
    t = proposal.get("terms") or {}
    amount_cents = int(round(float(t.get("price_monthly") or 0) * 100))
    if amount_cents <= 0:
        return {}
    client = await db.shop_clients.find_one({"_id": _oid(proposal["client_id"])}) or {}
    email = (proposal.get("signer") or {}).get("email") or proposal.get("contact_email") or client.get("contact_email")
    if not email:
        return {}
    cust_id = (client.get("billing") or {}).get("stripe_customer_id")
    if not cust_id:
        cust = await asyncio.to_thread(stripe.Customer.create, email=email, name=client.get("name") or proposal.get("client_name"), metadata={"shop_client_id": str(client.get("_id")), "managed_by": "imos_mystery_shop"})
        cust_id = cust.id
        await db.shop_clients.update_one({"_id": client["_id"]}, {"$set": {"billing.stripe_customer_id": cust_id}})
    inv_kwargs = dict(customer=cust_id, collection_method="send_invoice", days_until_due=7, auto_advance=True,
                      description=f"Mystery shop program for {client.get('name')}: {per_month_text(terms_per_month(t))} shops per month.",
                      metadata={"proposal_id": str(proposal["_id"]), "shop_client_id": str(client.get("_id"))})
    inv_kwargs.update(invoice_extras(client))
    try:
        inv = await asyncio.to_thread(stripe.Invoice.create, **inv_kwargs)
    except Exception as e:
        # iDEAL / SEPA not activated on the Stripe account yet: send a plain card invoice rather than nothing
        logger.warning(f"[MysteryShop] Stripe invoice with local payment methods failed, retrying plain: {e}")
        inv_kwargs.pop("payment_settings", None)
        inv = await asyncio.to_thread(stripe.Invoice.create, **inv_kwargs)
    await asyncio.to_thread(stripe.InvoiceItem.create, customer=cust_id, invoice=inv.id, amount=amount_cents, currency=loc.currency(loc.key_of(client)), description="Phone mystery shopping, first month")
    inv = await asyncio.to_thread(stripe.Invoice.finalize_invoice, inv.id)
    try:
        inv = await asyncio.to_thread(stripe.Invoice.send_invoice, inv.id)
    except Exception as e:
        logger.warning(f"[MysteryShop] Stripe send_invoice failed (hosted link still works): {e}")
    info = {"stripe_invoice_id": inv.id, "hosted_invoice_url": inv.hosted_invoice_url, "invoice_pdf": getattr(inv, "invoice_pdf", None), "status": inv.status, "amount": amount_cents / 100, "sent_at": _now().isoformat()}
    await db.shop_proposals.update_one({"_id": proposal["_id"]}, {"$set": {"invoice": info, "updated_at": _now()}})
    await db.shop_clients.update_one({"_id": client["_id"]}, {"$set": {"billing.last_invoice": info, "billing.status": "invoiced"}})
    return info


async def refresh_invoice(db, proposal: dict) -> dict:
    inv_id = (proposal.get("invoice") or {}).get("stripe_invoice_id")
    if not inv_id:
        return proposal.get("invoice") or {}
    try:
        inv = await asyncio.to_thread(_stripe().Invoice.retrieve, inv_id)
    except Exception as e:
        logger.debug(f"[MysteryShop] invoice refresh failed: {e}")
        return proposal.get("invoice") or {}
    info = {**(proposal.get("invoice") or {}), "status": inv.status, "hosted_invoice_url": inv.hosted_invoice_url, "paid_at": _now().isoformat() if inv.status == "paid" and not (proposal.get("invoice") or {}).get("paid_at") else (proposal.get("invoice") or {}).get("paid_at")}
    if info != proposal.get("invoice"):
        await db.shop_proposals.update_one({"_id": proposal["_id"]}, {"$set": {"invoice": info, **({"status": "paid"} if inv.status == "paid" else {})}})
        if inv.status == "paid":
            await db.shop_clients.update_one({"_id": _oid(proposal["client_id"])}, {"$set": {"billing.status": "paid", "billing.last_invoice": info}})
    return info


async def mark_invoice_paid(db, stripe_invoice_id: str):
    p = await db.shop_proposals.find_one({"invoice.stripe_invoice_id": stripe_invoice_id})
    if not p:
        return
    now = _now()
    await db.shop_proposals.update_one({"_id": p["_id"]}, {"$set": {"invoice.status": "paid", "invoice.paid_at": now.isoformat(), "status": "paid", "updated_at": now}})
    await db.shop_clients.update_one({"_id": _oid(p["client_id"])}, {"$set": {"billing.status": "paid", "billing.last_invoice.status": "paid", "billing.last_paid_at": now}})


# ---------------------------------------------------------------- proposal email + store kickoff
TIMEZONES = [("America/New_York", "Eastern"), ("America/Chicago", "Central"), ("America/Denver", "Mountain"), ("America/Phoenix", "Arizona"), ("America/Los_Angeles", "Pacific"), ("America/Anchorage", "Alaska"), ("Pacific/Honolulu", "Hawaii"),
             ("Europe/Amsterdam", "Nederland"), ("Europe/Brussels", "België"), ("Europe/London", "United Kingdom"), ("Europe/Dublin", "Ireland")]
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "imos-logo-email-168.png")


def logo_b64() -> str:
    try:
        import base64
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        logger.warning(f"[MysteryShop] logo missing: {e}")
        return ""


def _esc(v: str) -> str:
    return (v or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def money_text(amount: float, locale: Optional[str]) -> str:
    """'$400' / '€ 400' / '€ 1.250' the way the client's country writes it."""
    sym = loc.get(locale)["symbol"]
    s = f"{float(amount or 0):,.0f}"
    return f"{sym}{s}" if loc.language(locale) == "en" else f"{sym} {s}".replace(",", ".")


def proposal_email(p: dict, sender_name: str, note: str, url: str, logo_src: str, locale: Optional[str] = None) -> tuple:
    """(subject, html) for the proposal email in the client's language. logo_src is a data: URI for the in-app preview and cid:imos-logo when sending."""
    t = p.get("terms") or {}
    lang = loc.dialect(locale)
    tr = lambda k, **kw: i18n.t(lang, k, **kw)
    first = (p.get("contact_name") or "").strip().split(" ")[0] or ("daar" if lang == "nl" else "there")
    note_html = "".join(f'<p style="font-size:15px;line-height:1.65;margin:0 0 14px;color:#1a1a1a">{_esc(line)}</p>' for line in no_em_dash(note or "").strip().split("\n") if line.strip())
    logo = f'<img src="{logo_src}" alt="I\'m On Social" width="96" height="96" style="width:96px;height:96px;display:block;margin:0 auto" />' if logo_src else ""
    per_text = per_month_text_for(terms_per_month(t), locale, " and " if loc.language(locale) == "en" else " en ")
    html = f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f5f3ee">
  <div style="background:#fff;border-radius:18px;overflow:hidden;border:1px solid #e6e1d6">
    <div style="text-align:center;padding:30px 20px 18px;border-bottom:1px solid #eee">{logo}
      <p style="margin:12px 0 0;font-size:11px;letter-spacing:2px;color:#C9A962;font-weight:800">I'M ON SOCIAL</p>
    </div>
    <div style="padding:28px 30px">
      <h1 style="font-size:22px;line-height:1.3;margin:0 0 16px;color:#111">{_esc(tr("pmail.title", client=p.get('client_name')))}</h1>
      <p style="font-size:15px;line-height:1.65;margin:0 0 14px;color:#1a1a1a">{_esc(tr("pmail.hi", name=first))}</p>
      {note_html}
      <p style="font-size:15px;line-height:1.65;margin:0 0 14px;color:#1a1a1a">{tr("pmail.body", per=_esc(per_text), price=_esc(money_text(t.get('price_monthly') or 0, locale)))}</p>
      <p style="margin:26px 0;text-align:center"><a href="{url}" style="background:#C9A962;color:#111;text-decoration:none;font-weight:800;padding:14px 26px;border-radius:12px;display:inline-block;font-size:15px">{_esc(tr("pmail.button"))}</a></p>
      <p style="font-size:13px;color:#666;line-height:1.6;margin:0 0 18px">{_esc(tr("pmail.small"))}</p>
      <p style="font-size:14px;color:#333;line-height:1.5;margin:0">{_esc(sender_name or "Forest")}<br><span style="color:#888">I'm On Social</span></p>
    </div>
  </div>
  <p style="text-align:center;margin:18px 0 0;color:#999;font-size:12px">I'm On Social LLC · 1741 Lunford Ln, Riverton, UT 84065</p>
</div>"""
    return tr("pmail.subject", client=p.get('client_name')), html


async def ensure_kickoff_token(db, client: dict) -> str:
    tok = client.get("kickoff_token")
    if not tok:
        tok = uuid.uuid4().hex
        await db.shop_clients.update_one({"_id": client["_id"]}, {"$set": {"kickoff_token": tok}})
        client["kickoff_token"] = tok
    return tok


def kickoff_url(client: dict) -> Optional[str]:
    return f"{scr._app_url()}/shop-kickoff/{client['kickoff_token']}" if client.get("kickoff_token") else None


async def notify_kickoff(db, client: dict, people_added: int, people_total: int):
    """Tell the iMOS admins who own this client that the store filled in its kickoff form."""
    from routers.push_notifications import send_push_to_user
    from routers.notifications_center import invalidate_feed
    uids = {client.get("created_by")}
    latest = await db.shop_proposals.find_one({"client_id": str(client["_id"])}, sort=[("created_at", -1)])
    if latest and latest.get("sender_id"):
        uids.add(latest["sender_id"])
    uids.discard(None)
    title = f"{client.get('name')} set up their store"
    msg = f"{people_total} people to shop ({people_added} new), hours {_hours(client)['start']} to {_hours(client)['end']}. Tap to review."
    link = f"/admin/mystery-shops/{client['_id']}?tab=people"
    now = _now()
    for uid in uids:
        await db.notifications.insert_one({"user_id": uid, "type": "shop_kickoff", "title": title, "message": msg, "link": link, "read": False, "dismissed": False, "created_at": now})
        invalidate_feed(uid)
        try:
            await send_push_to_user(uid, title, msg, link, "storefront")
        except Exception as e:
            logger.debug(f"[MysteryShop] kickoff push failed for {uid}: {e}")


# ---------------------------------------------------------------- quick shops (anyone, no client account) + texting the scorecard
DEMO_CLIENT_NAME = "Quick shops"
QUICK_NOTES = "Built-in bucket for quick shops: anyone you shop without a client account lands here. Never billed."


async def rename_legacy_quick_bucket(db):
    await db.shop_clients.update_many({"demo": True, "name": {"$ne": DEMO_CLIENT_NAME}}, {"$set": {"name": DEMO_CLIENT_NAME, "notes": QUICK_NOTES}})
    await db.shop_clients.update_many({"demo": True, "$or": [{"hours": {"$ne": ALWAYS_OPEN}}, {"active": {"$ne": True}}]}, {"$set": {"hours": dict(ALWAYS_OPEN), "active": True}})


async def ensure_demo_client(db, me: dict) -> dict:
    """Built-in, never-billed bucket so Forest can shop anyone on the spot without creating a client first."""
    await rename_legacy_quick_bucket(db)
    c = await db.shop_clients.find_one({"demo": True})
    if c:
        return c
    now = _now()
    doc = {"name": DEMO_CLIENT_NAME, "demo": True, "brand": "", "city": "", "state": "", "timezone": "America/Denver", "contact_name": "", "contact_email": "", "contact_phone": "", "contact_title": "",
           "plan": {"per_month": {}, "price_monthly": 0.0}, "hours": dict(ALWAYS_OPEN), "vehicles": [], "active": True, "industry": "automotive",
           "record_calls": True, "notes": QUICK_NOTES, "text_scorecards": True, "report_token": uuid.uuid4().hex, "billing": {},
           "created_by": str(me["_id"]), "created_at": now, "updated_at": now}
    res = await db.shop_clients.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


async def demo_shop(db, me: dict, name: str, phone: str, department: str, title: str, store_name: str, vehicle: str, script: Optional[dict], text_scorecard: bool, industry: Optional[str] = None, mode: str = "phone", email: str = "") -> dict:
    c = await ensure_demo_client(db, me)
    industry = industry if industry in ind.INDUSTRIES else ind.industry_of_dept(department)
    cid, now = str(c["_id"]), _now()
    email = (email or "").strip().lower()
    t = await db.shop_targets.find_one({"client_id": cid, "phone": phone})
    if t:
        await db.shop_targets.update_one({"_id": t["_id"]}, {"$set": {"name": name, "department": department, "title": title, "active": True, "updated_at": now, **({"email": email} if email else {})}})
        t = {**t, "name": name, "department": department, "title": title, **({"email": email} if email else {})}
    else:
        res = await db.shop_targets.insert_one({"client_id": cid, "name": name, "phone": phone, "email": email, "department": department, "title": title, "notes": "Quick shop", "active": True, "challenge_history": [], "created_at": now, "updated_at": now})
        t = await db.shop_targets.find_one({"_id": res.inserted_id})
    place = f"your {ind.get(industry)['business']}"
    persona_client = {**c, "industry": industry, "name": store_name or place, "vehicles": [vehicle] if vehicle else []}
    call = await create_shop_call(db, persona_client, t, now, created_by=str(me["_id"]), manual=True, script=script, mode=mode)
    if not call:
        return {"error": f"No {ind.dept_label(department)} challenges for {ind.get(industry)['label']} yet. Open the Challenge Library and let Jessi write the starters."}
    await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"demo": True, "notify_sms": bool(text_scorecard), "store_name": store_name or f"the {ind.get(industry)['business']}"}})
    ok = await dial_now(db, {**call, "demo": True})
    s = await db.roleplay_sessions.find_one({"_id": call["_id"]})
    return {"ok": ok, "call": s, "client_id": cid}


def _short_criteria(ev: dict, passed: bool, n: int = 2) -> list:
    return [r.get("text", "").strip().rstrip(".") for r in (ev.get("results") or []) if bool(r.get("passed")) is passed and r.get("text")][:n]


def scorecard_sms(s: dict, ev: dict, url: str, course_line: str = "", lang: str = "en") -> str:
    tr = lambda k, **kw: i18n.t(lang, k, **kw)
    first = (s.get("rep_name") or "").split(" ")[0] or ("daar" if lang == "nl" else "there")
    pct = ev.get("score_pct")
    store = "" if s.get("demo") else tr("sms.for", store=str(s.get("store_name") or ("jullie vestiging" if lang == "nl" else "your store")))
    text = s.get("mode") == "text"
    email = s.get("mode") == "email"
    lines = [tr("sms.intro_email" if email else "sms.intro_text" if text else "sms.intro", name=first, store=store) + " " + (tr("sms.scored", pct=int(pct)) if pct is not None else tr("sms.ready"))]
    good, fix = _short_criteria(ev, True), _short_criteria(ev, False)
    if good:
        lines.append(tr("sms.nailed", items=", ".join(good)))
    if fix:
        lines.append(tr("sms.workon", items=", ".join(fix)))
    if course_line:
        lines.append(course_line)
    lines.append(tr("sms.link_text" if (text or email) else "sms.link", url=url))
    return no_em_dash("\n".join(lines))


async def _course_line(db, s: dict, pct, lang: str = "en") -> str:
    if not s.get("enrollment_id") or not ObjectId.is_valid(str(s["enrollment_id"])):
        return ""
    e = await db.course_enrollments.find_one({"_id": ObjectId(s["enrollment_id"])})
    course = await db.courses.find_one({"_id": ObjectId(e["course_id"])}) if e else None
    if not e or not course:
        return ""
    ids = course.get("challenge_ids") or []
    done = len([x for x in ids if ((e.get("progress") or {}).get(x) or {}).get("passed")])
    need = int(course.get("pass_pct") or 80)
    this_passed = pct is not None and pct >= need
    return i18n.t(lang, "sms.course", course=course.get('title'), done=done, total=len(ids)) + ("" if this_passed else i18n.t(lang, "sms.course_retry", need=need))


async def after_graded(db, sid: str):
    """Grading just finished for a shop call: give it a public scorecard link, text the person if wanted, ping the admin who set it up."""
    s = await db.roleplay_sessions.find_one({"_id": ObjectId(sid)})
    if not s or s.get("kind") != "mystery_shop" or s.get("status") != "completed":
        return
    client = await db.shop_clients.find_one({"_id": _oid(s["client_id"])}) or {}
    ev = await db.call_evaluations.find_one({"_id": ObjectId(s["evaluation_id"])}) if s.get("evaluation_id") and ObjectId.is_valid(str(s["evaluation_id"])) else None
    if not ev:
        return
    token = s.get("score_token") or uuid.uuid4().hex
    if not s.get("score_token"):
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"score_token": token}})
    url = f"{scr._app_url()}/shop-score/{token}"
    want_sms = s.get("notify_sms") if s.get("notify_sms") is not None else bool(client.get("text_scorecards") or s.get("enrollment_id"))
    if want_sms and s.get("rep_phone") and not s.get("score_sms_sent_at"):
        from services.twilio_service import send_sms
        lang = loc.dialect(s.get("locale") or loc.key_of(client))
        try:
            r = await send_sms(s["rep_phone"], scorecard_sms(s, ev, url, await _course_line(db, s, ev.get("score_pct"), lang), lang), from_phone=(s.get("from_number") or await from_number(db, client)) or None)
            await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"score_sms_sent_at": _now(), "score_sms_sid": (r or {}).get("sid") or (r or {}).get("message_sid"), "score_sms_status": (r or {}).get("status") or "sent"}})
        except Exception as e:
            logger.warning(f"[MysteryShop] scorecard text failed for {sid}: {e}")
            await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"score_sms_status": "failed", "score_sms_error": str(e)[:200]}})
    if s.get("created_by") and not s.get("graded_notified_at"):
        from routers.push_notifications import send_push_to_user
        from routers.notifications_center import invalidate_feed
        first = (s.get("rep_name") or "").split(" ")[0] or "The rep"
        pct = ev.get("score_pct")
        title = f"{first} scored {int(pct)}% on the shop" if pct is not None else f"{first}'s shop call is graded"
        msg = (ev.get("summary") or "")[:160] + (" Scorecard texted to them." if want_sms else "")
        link = f"/admin/mystery-shops/{s['client_id']}?tab=calls"
        await db.notifications.insert_one({"user_id": s["created_by"], "type": "shop_graded", "title": title, "message": msg, "link": link, "read": False, "dismissed": False, "created_at": _now()})
        invalidate_feed(s["created_by"])
        try:
            await send_push_to_user(s["created_by"], title, msg, link, "storefront")
        except Exception as e:
            logger.debug(f"[MysteryShop] graded push failed: {e}")
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"graded_notified_at": _now()}})


def public_score(s: dict, ev: dict, client: dict) -> dict:
    first = (s.get("rep_name") or "").split(" ")[0]
    industry = s.get("industry") or ind.industry_of_dept(s.get("department"))
    lc = s.get("locale") or loc.key_of(client)
    pack = ind.translated(industry, lc)
    return {"first_name": first, "name": s.get("rep_name"), "department": s.get("department"), "department_label": ind.dept_label_for(s.get("department"), lc, industry), "customer_noun": pack["customer"],
            "language": loc.dialect(lc), "locale": lc,
            "store_name": None if s.get("demo") else (s.get("store_name") or client.get("name")), "demo": bool(s.get("demo")),
            "challenge_title": s.get("script_title"), "persona_name": (s.get("persona") or {}).get("name"), "score_pct": ev.get("score_pct"), "scorecard_name": ev.get("scorecard_name"), "summary": ev.get("summary") or "",
            "wins": ev.get("wins") or [], "coaching": ev.get("coaching") or [], "customer_sentiment": ev.get("customer_sentiment") or "",
            "results": [{"text": r.get("text"), "passed": bool(r.get("passed")), "critical": bool(r.get("critical")), "evidence": r.get("evidence") or ""} for r in (ev.get("results") or [])],
            "recording_url": s.get("recording_url"), "recording_seconds": s.get("recording_seconds"), "ended_at": s["ended_at"].isoformat() if s.get("ended_at") else None,
            "adherence": {k: (ev.get("adherence") or {}).get(k) for k in ("score_pct", "hits", "misses", "summary")},
            "channel": s.get("mode") if s.get("mode") in ("text", "email") else "call", "text": tx.stats(s) if s.get("mode") in ("text", "email") else None, "transcript_turns": tx.transcript_turns(s) if s.get("mode") in ("text", "email") else None,
            "subject": s.get("subject") if s.get("mode") == "email" else None}


# ---------------------------------------------------------------- AI challenge generator
VOICES = ("female", "male", "young", "older")


def _plain(v, n: int) -> str:
    return no_em_dash("; ".join(str(x) for x in v) if isinstance(v, list) else str(v or "")).replace("{", "").replace("}", "")[:n].strip()


def normalize_draft(d: dict, department: str) -> Optional[dict]:
    """Coerce one model draft into the challenge shape the pool and the editor expect. Placeholders {vehicle}/{store} are allowed only in persona text."""
    body = d.get("body")
    if isinstance(body, list):
        body = "\n\n".join(str(x).strip() for x in body if str(x).strip())
    if not isinstance(d, dict) or not str(d.get("title") or "").strip() or not str(body or "").strip():
        return None
    persona = d.get("persona") if isinstance(d.get("persona"), dict) else {}
    ptxt = lambda v, n: no_em_dash(str(v or ""))[:n].strip()
    return {
        "title": _plain(d.get("title"), 120), "department": department, "runtime": _plain(d.get("runtime"), 40) or "3 to 5 min", "purpose": _plain(d.get("purpose"), 400), "body": no_em_dash(str(body))[:8000].strip(),
        "success_points": [_plain(p, 160) for p in (d.get("success_points") or []) if str(p).strip()][:12],
        "curveballs": [_plain(c, 160) for c in (d.get("curveballs") or []) if str(c).strip()][:4],
        "persona": {"name": _plain(persona.get("name"), 60) or "Jordan Lee", "voice": persona.get("voice") if persona.get("voice") in VOICES else "female", "summary": ptxt(persona.get("summary"), 400),
                    "goals": ptxt(persona.get("goals"), 200), "objections": [ptxt(o, 160) for o in (persona.get("objections") or []) if str(o).strip()][:6], "opening_line": ptxt(persona.get("opening_line"), 240)},
    }


async def generate_challenges(department: str, scenario: str, count: int = 1, client: Optional[dict] = None, industry: Optional[str] = None) -> list:
    """Forest describes a situation in plain words; Jessi drafts count distinct challenges (persona, opening line, what a great rep does, graded points, curveballs). Nothing is saved."""
    count = max(1, min(5, int(count or 1)))
    industry = industry if industry in ind.INDUSTRIES else ind.industry_of_dept(department)
    pack, d = ind.get(industry), ind.dept(department, industry)
    off = pack["offering"]
    store = f" The client is {client.get('name')}{' (' + client.get('brand') + ')' if client.get('brand') else ''}." if client else ""
    system = (f"You are Jessi, a {pack['trainer']} who writes mystery-shop challenges for {pack['label'].lower()} teams. A challenge is a realistic phone call the AI {pack['customer']} will act out against a real employee ({d['rep']}), then grade. "
              f"Department context: {d['brief']}.{store} "
              f"Write {count} DISTINCT challenge{'s' if count > 1 else ''} from the scenario below (vary the person, the wrinkle and the emotional tone; do not repeat the same caller twice). "
              f"Each challenge: title (short, starts with '{d['prefix']}'), runtime like '3 to 5 min', "
              "purpose (one or two sentences: what the situation is and what a great rep does), "
              f"body (a STRING, the coaching guide written TO THE REP in second person: 'Answer with the {pack['business']} and your name', 4 to 7 short paragraphs separated by blank lines, stage directions in [brackets]; this is what we grade the rep against, it is NOT the caller's lines; plain words, no curly braces), "
              f"success_points (5 to 8 graded rep behaviours, each 4 to 12 words starting with a verb, e.g. 'Confirms the exact {off['label']}'), curveballs (2 to 3 short second-person twists the caller may throw in, e.g. 'You only have two minutes'), "
              f"persona: name (first and last), voice one of female/male/young/older, summary (age, job, situation, mood; you MAY write {{offering}} for the {off['label']} they ask about and {{store}} for the {pack['business']} name), "
              "goals (one sentence), objections (2 to 4 things they push back with), opening_line (the exact first thing they say when the rep answers; may use {offering} and {store}). "
              "Sound like a real person on the phone, never corporate. Never use em dashes. "
              "Return JSON: {\"challenges\": [{title, runtime, purpose, body, success_points:[...], curveballs:[...], persona:{name, voice, summary, goals, objections:[...], opening_line}}]}")
    data = await scr._llm_json(system, f"SCENARIO ({pack['label']} / {d['label']}):\n{scenario.strip()[:3000]}", timeout=120)
    raw = data.get("challenges") if isinstance(data, dict) else None
    if isinstance(data, dict) and not raw and data.get("title"):
        raw = [data]
    drafts = [x for x in (normalize_draft(d, department) for d in (raw or [])) if x]
    if not drafts:
        raise ValueError("Jessi could not turn that into a challenge, try adding a little more detail")
    return drafts[:count]


async def seed_starters(db, me: dict, industry: str, department: Optional[str] = None, per_department: int = 2) -> list:
    """Jessi writes the starter challenges for an industry (or one department) from the pack briefs and saves them to the global library, flagged so the admin can review."""
    industry = industry if industry in ind.INDUSTRIES else ind.DEFAULT_INDUSTRY
    made = []
    for d in ind.departments(industry):
        if department and d["key"] != department:
            continue
        have = await db.scripts.count_documents({"pool": "mystery_shop", "shop_client_id": None, "department": d["key"], "active": {"$ne": False}})
        if have >= per_department:
            continue
        scenario = f"Write the everyday, most common versions of this call for a {ind.get(industry)['label'].lower()} team: {d['brief']}. Typical curveballs: {'; '.join(d.get('curveballs', [])[:3])}."
        drafts = await generate_challenges(d["key"], scenario, per_department - have, None, industry)
        for x in drafts:
            doc = {"kind": "phone", "pool": "mystery_shop", "industry": industry, "shop_client_id": None, "store_id": None, "slug": f"shop_starter_{ObjectId()}", "direction": "inbound", "category": d["label"], "active": True,
                   "generated_from": "starter", "created_by": str(me["_id"]), "created_at": _now(), "updated_at": _now(), **x}
            res = await db.scripts.insert_one(doc)
            doc["_id"] = res.inserted_id
            made.append(doc)
    return made


# ---------------------------------------------------------------- other languages: Jessi adapts the English library, a native speaker approves
LANGUAGE_NAMES = {"nl": "Dutch (Netherlands)", "en-GB": "British English (UK & Ireland)"}
LANGUAGE_LOCALE = {"nl": "nl-NL", "en-GB": "en-GB"}
LANGUAGE_EXTRA = {
    "nl": ("Dutch specifics: Dutch first and last names (Sanne de Vries, Pieter Bakker), Dutch towns, prices in euro written like 18.950 or 132,89, Dutch car culture and words "
           "(APK, inruil, occasion, proefrit, private lease, bijtelling, rijklaarmaakkosten, kenteken, dealer, werkplaats, onderdelen, schadeherstel, huurauto), informal 'je' unless the persona is clearly formal. runtime like '3 tot 4 min'. "),
    "en-GB": ("British specifics: British first and last names (Sophie Walker, Tom Hughes), UK towns, prices in pounds written like £18,950 or £132.89, mileage in miles, British spelling (colour, tyre, organise), "
              "UK motor trade words: part exchange (never trade-in), MOT, reg plate (never VIN or license plate), bonnet, boot, tyres, windscreen, forecourt, screen price (never sticker price or MSRP), "
              "a deposit and monthlies on PCP or HP finance, road tax, service plan, courtesy car, postcode (never ZIP), mobile (never cell), sorted, cheers. runtime like '3 to 4 min'. "),
}


def localize_job_key(language: str) -> str:
    return f"localize_job_{language}"


async def localize_status(db, language: str) -> dict:
    job = await db.settings.find_one({"key": localize_job_key(language)}) or {}
    return {k: job.get(k) for k in ("status", "made", "total", "started_at", "finished_at", "error") if k in job}


async def review_summary(db, language: str, industry: Optional[str] = None) -> dict:
    """How many localized challenges exist, how many still wait for the native reviewer, per department."""
    q = {"kind": "phone", "pool": "mystery_shop", "shop_client_id": None, "active": {"$ne": False}, **language_filter(language)}
    if industry:
        q["industry"] = industry
    rows = await db.scripts.find(q, {"title": 1, "department": 1, "review": 1, "persona.name": 1, "source_slug": 1, "updated_at": 1}).sort([("department", 1), ("title", 1)]).to_list(500)
    pending = [r for r in rows if (r.get("review") or {}).get("status") == "needs_review"]
    by_dept: dict = {}
    for r in rows:
        d = by_dept.setdefault(r.get("department"), {"total": 0, "pending": 0})
        d["total"] += 1
        d["pending"] += 1 if (r.get("review") or {}).get("status") == "needs_review" else 0
    src = await db.scripts.count_documents({"kind": "phone", "pool": "mystery_shop", "shop_client_id": None, "active": {"$ne": False}, "industry": industry or ind.DEFAULT_INDUSTRY, **language_filter("en")})
    return {"language": language, "language_label": LANGUAGE_NAMES.get(language, language), "total": len(rows), "pending": len(pending), "approved": len(rows) - len(pending), "source_total": src,
            "by_department": by_dept, "job": await localize_status(db, language),
            "pending_items": [{"id": str(r["_id"]), "title": r.get("title"), "department": r.get("department"), "persona": (r.get("persona") or {}).get("name", "")} for r in pending][:60]}


async def set_review(db, script_id: str, status: str, me: dict) -> dict:
    if status not in ("approved", "needs_review"):
        raise ValueError("status must be approved or needs_review")
    now = _now()
    res = await db.scripts.find_one_and_update({"_id": _oid(script_id), "pool": "mystery_shop"}, {"$set": {"review": {"status": status, "by": str(me["_id"]), "by_name": me.get("name") or "", "at": now}, "updated_at": now}}, return_document=True)
    if not res:
        raise ValueError("Challenge not found")
    return res


async def approve_all(db, language: str, me: dict) -> int:
    now = _now()
    r = await db.scripts.update_many({"kind": "phone", "pool": "mystery_shop", "review.status": "needs_review", **language_filter(language)},
                                     {"$set": {"review": {"status": "approved", "by": str(me["_id"]), "by_name": me.get("name") or "", "at": now}, "updated_at": now}})
    return r.modified_count


def _localize_system(language: str, industry: str, dept: dict, n: int) -> str:
    lang_name = LANGUAGE_NAMES.get(language, language)
    pack = ind.translated(industry, LANGUAGE_LOCALE.get(language))
    extra = LANGUAGE_EXTRA.get(language, "")
    return (f"You are Jessi, a native {lang_name} speaking sales trainer for {pack['label'].lower()} teams. You ADAPT English mystery-shop phone challenges into natural {lang_name} for a {lang_name} {pack['business']}: "
            f"not a literal translation, the way a local trainer would write it. {extra}"
            f"EVERY text field must come out in {lang_name}: title, purpose, body, every success_point, every curveball, and the whole persona (give the persona a typical {lang_name} first and last name, and write summary, goals, objections and opening_line in {lang_name}). "
            f"Leaving any of those in the original American wording is a failure. Keep the MEANING of each success point and curveball (same count, same order), the persona's age/mood/situation, and the placeholders {{vehicle}} and {{store}} exactly as written (they are filled in later); source_slug and persona.voice are copied unchanged. "
            f"Titles start with '{dept.get('prefix') or dept['label'] + ':'}'. body is a STRING written TO THE REP in second person, 4 to 7 short paragraphs separated by blank lines, no curly braces except the placeholders. "
            f"persona.voice stays one of female/male/young/older. Never use em dashes. Sound like a real person on the phone, never corporate. "
            f"Return JSON: {{\"challenges\": [{{source_slug, title, runtime, purpose, body, success_points:[...], curveballs:[...], persona:{{name, voice, summary, goals, objections:[...], opening_line}}}}]}} with exactly {n} items, one per source_slug, in the same order.")


async def localize_starters(db, me: dict, language: str = "nl", industry: str = "automotive", department: Optional[str] = None) -> dict:
    """Background job: for every English global challenge without a {language} twin, Jessi writes the adapted version, flagged needs_review."""
    key = localize_job_key(language)
    now = _now()
    src_q = {"kind": "phone", "pool": "mystery_shop", "shop_client_id": None, "active": {"$ne": False}, "industry": industry, **language_filter("en")}
    if department:
        src_q["department"] = department
    sources = await db.scripts.find(src_q).sort([("department", 1), ("title", 1)]).to_list(200)
    have = {r.get("source_slug") for r in await db.scripts.find({"pool": "mystery_shop", "language": language, "source_slug": {"$ne": None}}, {"source_slug": 1}).to_list(500)}
    todo = [s for s in sources if s.get("slug") and s["slug"] not in have]
    await db.settings.update_one({"key": key}, {"$set": {"status": "running", "made": 0, "total": len(todo), "started_at": now, "error": None, "finished_at": None}}, upsert=True)
    made = 0
    try:
        by_dept: dict = {}
        for s_ in todo:
            by_dept.setdefault(s_.get("department") or "sales", []).append(s_)
        for dept_key, items in by_dept.items():
            d = ind.translated(industry, LANGUAGE_LOCALE.get(language))["departments"]
            dpack = next((x for x in d if x["key"] == dept_key), d[0])
            for i in range(0, len(items), 3):
                batch = items[i:i + 3]
                user = "\n\n".join(f"SOURCE {x['slug']}:\n" + json.dumps({k: x.get(k) for k in ("title", "runtime", "purpose", "body", "success_points", "curveballs", "persona")}, ensure_ascii=False) for x in batch)
                data = await scr._llm_json(_localize_system(language, industry, dpack, len(batch)), user, timeout=180)
                raw = data.get("challenges") if isinstance(data, dict) else None
                for x in raw or []:
                    src = next((b for b in batch if b["slug"] == x.get("source_slug")), None) or (batch[(raw or []).index(x)] if len(raw or []) == len(batch) else None)
                    if not src:
                        continue
                    draft = normalize_draft(x, dept_key)
                    if not draft:
                        continue
                    doc = {"kind": "phone", "pool": "mystery_shop", "industry": industry, "shop_client_id": None, "store_id": None, "slug": f"{src['slug']}_{language}", "source_slug": src["slug"], "language": language,
                           "direction": src.get("direction") or "inbound", "category": dpack["label"], "active": True, "generated_from": "localized", "review": {"status": "needs_review", "at": _now()},
                           "created_by": str(me["_id"]), "created_at": _now(), "updated_at": _now(), **draft}
                    await db.scripts.update_one({"slug": doc["slug"]}, {"$setOnInsert": doc}, upsert=True)
                    made += 1
                await db.settings.update_one({"key": key}, {"$set": {"made": made}})
        await db.settings.update_one({"key": key}, {"$set": {"status": "done", "made": made, "finished_at": _now()}})
    except Exception as e:
        logger.warning(f"[MysteryShop] localize {language} failed after {made}: {e}")
        await db.settings.update_one({"key": key}, {"$set": {"status": "error", "made": made, "error": str(e)[:300], "finished_at": _now()}})
    return {"made": made, "total": len(todo)}
