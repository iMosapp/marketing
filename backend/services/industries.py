"""Industry packs for Mystery Shops / practice calls. Everything that used to assume a car dealership reads from here:
the nouns Jessi uses, the departments an account can shop, what the AI caller can mention, the curveballs, and how each department is graded."""
from typing import Optional

DEFAULT_INDUSTRY = "automotive"

# offering = the thing the caller asks about ({vehicle} in the original automotive content; {offering} works everywhere)
INDUSTRIES: dict = {
    "automotive": {
        "label": "Automotive dealership", "business": "dealership", "place": "store", "customer": "shopper", "trainer": "dealership phone trainer",
        "offering": {"label": "vehicle", "plural": "vehicles", "hint": "2024 Jeep Grand Cherokee L Limited", "field": "Vehicles the shopper can mention", "field_help": "Real units from the lot make the calls believable. Year, make, model, trim is plenty."},
        "departments": [
            {"key": "sales", "label": "Sales", "call": "sales call", "prefix": "Shopper:", "rep": "a salesperson", "template": "phone_up",
             "brief": "an inbound sales phone-up at a car dealership; the rep should get the name and number, confirm the vehicle, ask about a trade and sell the visit, never quote payments blind",
             "curveballs": ["You already have a written quote from a competing store", "You only have 2 minutes, you are on a work break", "You want the payment over the phone before you will consider coming in",
                            "You are 45 minutes away and worried about wasting the drive", "Your spouse makes the final decision and is not with you", "You ask if the price online is negotiable"],
             "defaults": ["the used SUV you have listed online", "the pickup you have on your website"]},
            {"key": "service", "label": "Service", "call": "service call", "prefix": "Service caller:", "rep": "a service advisor", "template": "service_bdc",
             "brief": "an inbound service department call; the advisor should confirm the vehicle, identify the concern, offer the first available appointment, mention transportation, confirm the number and recap",
             "curveballs": ["You need a loaner or a ride because you work during the day", "You had a bad experience at another store and are skeptical", "You want to know the exact price before booking",
                            "You can only come in on Saturday", "The warning light just came on and you are nervous about driving it", "You ask whether the work is covered under warranty"],
             "defaults": ["my SUV", "my truck"]},
            {"key": "parts", "label": "Parts", "call": "parts call", "prefix": "Parts caller:", "rep": "a parts counterperson", "template": "parts_phone",
             "brief": "an inbound parts counter call; the parts person should confirm the exact vehicle (VIN, year, trim), check availability, quote clearly with what it includes, ask for the sale or offer to hold or order, get the number",
             "curveballs": ["You found the part cheaper online and say so", "You are not sure of the exact year or trim of your vehicle", "You need it today because the car is on a lift at an independent shop",
                            "You ask whether the aftermarket version is just as good", "You want it shipped instead of picking it up", "You are calling on behalf of your elderly parent"],
             "defaults": ["my SUV", "my truck"]},
            {"key": "rental", "label": "Rental", "call": "rental call", "prefix": "Rental caller:", "rep": "a rental agent", "template": "rental_phone",
             "brief": "an inbound rental desk call; the agent should ask dates and need, offer a specific vehicle, state the rate and what it includes, explain requirements, ask to reserve and confirm pickup",
             "curveballs": ["Your car is in the body shop and insurance is paying, you are not sure what they cover", "You need the vehicle in the next two hours", "You ask about one-way rentals to another city",
                            "You are under 25 and worry about the extra fee", "You want to know exactly what the deposit and mileage rules are", "You need a car seat or a tow hitch"],
             "defaults": ["a mid-size SUV", "a pickup"]},
            {"key": "collision", "label": "Body Shop", "call": "body shop call", "prefix": "Collision caller:", "rep": "a body shop estimator", "template": "collision_phone",
             "brief": "an inbound collision center call from someone whose vehicle was just damaged; the estimator should show empathy, confirm the vehicle, the damage and whether it is drivable, ask about the insurance claim, explain the estimate process instead of quoting blind, mention rental or transportation and set a specific estimate or drop-off time",
             "curveballs": ["The other driver's insurance is paying and you are not sure what that means for you", "Your own insurance told you to use their preferred shop", "You want a price over the phone from a couple of photos",
                            "You need a rental car today because it is your only vehicle", "You ask whether they use original parts or aftermarket", "You had a bad experience with a body shop that took six weeks last time"],
             "defaults": ["my SUV", "my sedan"]},
        ],
    },
    "real_estate": {
        "label": "Real estate", "business": "brokerage", "place": "office", "customer": "caller", "trainer": "real estate phone coach",
        "offering": {"label": "listing", "plural": "listings", "hint": "3 bed 2 bath on Maple Street, listed at 489k", "field": "Listings the caller can mention", "field_help": "Real active listings make the calls believable. Address or neighborhood and price is plenty."},
        "departments": [
            {"key": "re_buyer", "label": "Buyer leads", "call": "buyer call", "prefix": "Buyer:", "rep": "a real estate agent",
             "brief": "an inbound call from a buyer who saw a listing online or on a sign; the agent should get the name and number, learn timeline and financing status, ask what else they are looking at, and set a showing or consultation with two time options instead of just answering questions",
             "curveballs": ["You are already working with another agent, sort of", "You are not pre-approved yet and get defensive about it", "You only want to know the price and the HOA fee", "You are relocating and can only see homes this weekend", "Your parents are helping with the down payment and want to join", "You ask if the seller will take less"],
             "defaults": ["the house you have listed on Maple Street", "the condo you have listed downtown"],
             "scorecard": {"name": "Buyer Inquiry Call", "criteria": [
                 {"text": "Answered with their name and the brokerage", "hint": "Name and company, warm and unhurried.", "weight": 1, "critical": False},
                 {"text": "Got and used the caller's name", "hint": "Ask early, use it twice.", "weight": 1, "critical": False},
                 {"text": "Confirmed the listing they are calling about", "hint": "Repeat the address or neighborhood back.", "weight": 1, "critical": False},
                 {"text": "Asked about timeline and motivation", "hint": "When do they want to be moved in, and why now?", "weight": 2, "critical": False},
                 {"text": "Asked about financing or pre-approval", "hint": "Gently: 'Have you talked with a lender yet?'", "weight": 2, "critical": True},
                 {"text": "Asked for a showing or consultation with two time options", "hint": "'I can show it at 5:30 tonight or 10 tomorrow, which is better?'", "weight": 2, "critical": True},
                 {"text": "Got the caller's phone number", "hint": "Best cell in case you get disconnected.", "weight": 2, "critical": True},
                 {"text": "Recapped next steps and thanked the caller", "hint": "Who does what next, then a genuine thank you.", "weight": 1, "critical": False}]}},
            {"key": "re_seller", "label": "Seller leads", "call": "seller call", "prefix": "Seller:", "rep": "a listing agent",
             "brief": "an inbound call from a homeowner thinking about selling; the agent should learn the property, the timeline and the reason, avoid quoting a price blind, and set an in-person listing appointment",
             "curveballs": ["You want a number for your house right now over the phone", "You are interviewing three agents and say so", "You are thinking about selling it yourself", "You are not sure whether to sell or rent it out", "A relative is an agent in another state", "You had a bad experience with the last agent who listed it"],
             "defaults": ["my 4 bedroom in the Highlands", "my townhome near the university"],
             "scorecard": {"name": "Seller Inquiry Call", "criteria": [
                 {"text": "Answered with their name and the brokerage", "hint": "Name and company.", "weight": 1, "critical": False},
                 {"text": "Got and used the caller's name", "hint": "Ask early, use it.", "weight": 1, "critical": False},
                 {"text": "Learned the property basics (location, size, condition)", "hint": "Ask, do not guess.", "weight": 1, "critical": False},
                 {"text": "Asked about timeline and reason for selling", "hint": "Why now, and when do they need to be moved?", "weight": 2, "critical": False},
                 {"text": "Did not quote a value over the phone without seeing it", "hint": "Explain why a blind number would hurt them.", "weight": 2, "critical": True},
                 {"text": "Asked for an in-person listing appointment with two time options", "hint": "Two choices, then confirm.", "weight": 2, "critical": True},
                 {"text": "Got the caller's phone number", "hint": "Repeat it back.", "weight": 2, "critical": True},
                 {"text": "Recapped next steps and thanked the caller", "hint": "Close warm and clear.", "weight": 1, "critical": False}]}},
        ],
    },
    "home_services": {
        "label": "Home services", "business": "company", "place": "shop", "customer": "caller", "trainer": "home services phone coach",
        "offering": {"label": "service", "plural": "services", "hint": "AC not cooling, 2-story home, 12 year old unit", "field": "Services or systems the caller can mention", "field_help": "What you actually sell and fix: 'AC repair', 'water heater replacement', 'roof inspection'."},
        "departments": [
            {"key": "hs_repair", "label": "Repair calls", "call": "repair call", "prefix": "Caller:", "rep": "a customer service rep",
             "brief": "an inbound call from a homeowner with something broken (no AC, leaking water heater, roof leak); the CSR should show empathy, ask the right diagnostic questions, explain the dispatch or diagnostic fee clearly, book the first available window, confirm the address and number, and recap",
             "curveballs": ["It is 95 degrees and you have a baby in the house", "You ask for the exact repair price before anyone comes out", "You got a quote from another company already", "You can only be home after 5", "You rent and are not sure the landlord will pay", "You ask if the tech will try to sell you a new system"],
             "defaults": ["my air conditioner", "my water heater"],
             "scorecard": {"name": "Repair Call", "criteria": [
                 {"text": "Answered with their name and the company", "hint": "Name and company, calm and friendly.", "weight": 1, "critical": False},
                 {"text": "Got and used the caller's name", "hint": "Ask early, use it.", "weight": 1, "critical": False},
                 {"text": "Showed empathy for the problem", "hint": "Acknowledge before you diagnose.", "weight": 1, "critical": False},
                 {"text": "Asked diagnostic questions about the system and symptoms", "hint": "Age, symptoms, when it started.", "weight": 1, "critical": False},
                 {"text": "Explained the dispatch or diagnostic fee clearly", "hint": "Say the number and what it covers.", "weight": 2, "critical": True},
                 {"text": "Offered the first available appointment window", "hint": "Lead with the soonest, then alternatives.", "weight": 2, "critical": True},
                 {"text": "Confirmed the address and phone number", "hint": "Repeat both back.", "weight": 2, "critical": True},
                 {"text": "Recapped the appointment and what happens next", "hint": "Window, who is coming, how they will be notified.", "weight": 1, "critical": False}]}},
            {"key": "hs_estimate", "label": "Estimates", "call": "estimate call", "prefix": "Caller:", "rep": "a comfort advisor",
             "brief": "an inbound call from a homeowner wanting a quote for a replacement or install (new HVAC system, roof, solar, remodel); the rep should learn the home and the goal, avoid quoting a price blind, explain the free in-home estimate and financing options, and book the visit with two time options",
             "curveballs": ["You want a ballpark price before you will book anything", "You have two other estimates scheduled this week", "You ask whether financing is available", "Your spouse needs to be there and works odd hours", "You are not sure you need a whole new system", "You found a much cheaper price online"],
             "defaults": ["a new AC system", "a full roof replacement"],
             "scorecard": {"name": "Estimate Call", "criteria": [
                 {"text": "Answered with their name and the company", "hint": "Name and company.", "weight": 1, "critical": False},
                 {"text": "Got and used the caller's name", "hint": "Ask early, use it.", "weight": 1, "critical": False},
                 {"text": "Asked about the home and the goal of the project", "hint": "Size, age of system, what they want to solve.", "weight": 2, "critical": False},
                 {"text": "Handled the price question without a blind quote", "hint": "Explain what changes the number and offer the free estimate.", "weight": 2, "critical": True},
                 {"text": "Mentioned financing or payment options", "hint": "One sentence is enough.", "weight": 1, "critical": False},
                 {"text": "Booked the in-home estimate with two time options", "hint": "'Thursday at 4 or Saturday at 10?'", "weight": 2, "critical": True},
                 {"text": "Confirmed the address and phone number", "hint": "Repeat both back.", "weight": 2, "critical": True},
                 {"text": "Recapped next steps and thanked the caller", "hint": "Who comes, when, what to expect.", "weight": 1, "critical": False}]}},
            {"key": "hs_maintenance", "label": "Maintenance plans", "call": "maintenance call", "prefix": "Caller:", "rep": "a customer service rep",
             "brief": "an inbound call asking about a tune-up, seasonal maintenance or a membership plan; the rep should explain what the visit includes, present the maintenance plan value clearly, book the visit and confirm contact details",
             "curveballs": ["You only want the cheapest tune-up special you saw advertised", "You ask what the membership actually gets you", "You had a plan with another company and felt ripped off", "You want both the furnace and the AC done in one visit", "You are selling the house next month", "You can only do early mornings"],
             "defaults": ["my furnace", "my heat pump"],
             "scorecard": {"name": "Maintenance Call", "criteria": [
                 {"text": "Answered with their name and the company", "hint": "Name and company.", "weight": 1, "critical": False},
                 {"text": "Got and used the caller's name", "hint": "Ask early, use it.", "weight": 1, "critical": False},
                 {"text": "Explained what the maintenance visit includes", "hint": "Three or four concrete items.", "weight": 1, "critical": False},
                 {"text": "Presented the maintenance plan or membership value", "hint": "Priority service, discounts, no dispatch fee.", "weight": 2, "critical": True},
                 {"text": "Booked the visit with a specific window", "hint": "Two options, then confirm.", "weight": 2, "critical": True},
                 {"text": "Confirmed the address and phone number", "hint": "Repeat both back.", "weight": 2, "critical": True},
                 {"text": "Recapped and thanked the caller", "hint": "Close clear and warm.", "weight": 1, "critical": False}]}},
        ],
    },
    "medical_dental": {
        "label": "Medical, dental and med spa", "business": "practice", "place": "office", "customer": "patient", "trainer": "patient-experience phone coach",
        "offering": {"label": "treatment", "plural": "treatments", "hint": "Invisalign consult, new patient cleaning, Botox", "field": "Treatments or services the caller can mention", "field_help": "What patients actually call about: 'new patient exam', 'implant consult', 'laser hair removal'."},
        "departments": [
            {"key": "med_new_patient", "label": "New patients", "call": "new patient call", "prefix": "New patient:", "rep": "a front desk coordinator",
             "brief": "an inbound call from a prospective new patient; the coordinator should be warm, learn what brought them in, answer insurance and pricing questions honestly without a blind quote, explain what the first visit includes, book the appointment with two time options, and confirm phone and email",
             "curveballs": ["You ask if they take your insurance and get frustrated by vague answers", "You are in pain and want to be seen today", "You are anxious about the dentist and admit it", "You want the exact price of the procedure over the phone", "You are comparing two offices", "You need appointments for your whole family"],
             "defaults": ["a new patient exam and cleaning", "a consultation"],
             "scorecard": {"name": "New Patient Call", "criteria": [
                 {"text": "Answered with their name and the practice", "hint": "Name and practice, warm.", "weight": 1, "critical": False},
                 {"text": "Got and used the caller's name", "hint": "Ask early, use it.", "weight": 1, "critical": False},
                 {"text": "Asked what brought them in and showed empathy", "hint": "Listen first, especially with pain or anxiety.", "weight": 2, "critical": False},
                 {"text": "Handled the insurance or price question clearly and honestly", "hint": "Offer to verify benefits, explain what the first visit costs.", "weight": 2, "critical": True},
                 {"text": "Explained what the first visit includes", "hint": "Exam, x-rays, consult, how long.", "weight": 1, "critical": False},
                 {"text": "Offered an appointment with two time options", "hint": "Soonest first, then an alternative.", "weight": 2, "critical": True},
                 {"text": "Confirmed phone number and email", "hint": "For forms and reminders.", "weight": 2, "critical": True},
                 {"text": "Recapped and thanked the caller", "hint": "Day, time, what to bring, thank you.", "weight": 1, "critical": False}]}},
            {"key": "med_scheduling", "label": "Scheduling", "call": "scheduling call", "prefix": "Patient:", "rep": "a scheduling coordinator",
             "brief": "an inbound call from an existing patient who needs to book, move or cancel an appointment; the coordinator should verify the patient, protect the schedule by offering the next best slot instead of just cancelling, mention overdue care when relevant, and confirm details",
             "curveballs": ["You want to cancel and not reschedule", "You are running late and want to know if you should still come", "You need a specific provider only", "You ask why the wait for an appointment is so long", "You need a school or work excuse note", "You want to be squeezed in this week"],
             "defaults": ["my cleaning", "my follow-up visit"],
             "scorecard": {"name": "Scheduling Call", "criteria": [
                 {"text": "Answered with their name and the practice", "hint": "Name and practice.", "weight": 1, "critical": False},
                 {"text": "Verified the patient (name and date of birth)", "hint": "Every time, kindly.", "weight": 1, "critical": False},
                 {"text": "Offered a new time instead of just cancelling", "hint": "'Let's find the next spot that works.'", "weight": 2, "critical": True},
                 {"text": "Offered two specific time options", "hint": "Soonest, then one more.", "weight": 2, "critical": False},
                 {"text": "Mentioned any overdue or recommended care", "hint": "If they are due, say so warmly.", "weight": 1, "critical": False},
                 {"text": "Confirmed the phone number for reminders", "hint": "Repeat it back.", "weight": 2, "critical": True},
                 {"text": "Recapped the appointment and thanked the patient", "hint": "Day, time, provider.", "weight": 1, "critical": False}]}},
            {"key": "med_billing", "label": "Insurance and billing", "call": "billing call", "prefix": "Patient:", "rep": "a billing coordinator",
             "brief": "an inbound call about a bill, an insurance denial or a payment plan; the coordinator should stay calm, verify the patient, explain the charge in plain words, offer options (payment plan, resubmission, itemized statement), and set a clear next step with a date",
             "curveballs": ["You are angry about a surprise bill", "You insist your insurance should have covered it", "You cannot pay the full amount this month", "You want an itemized statement emailed today", "You threaten to leave a bad review", "You are calling for your elderly mother"],
             "defaults": ["the statement I got in the mail", "my last visit"],
             "scorecard": {"name": "Billing Call", "criteria": [
                 {"text": "Answered with their name and the practice", "hint": "Name and practice.", "weight": 1, "critical": False},
                 {"text": "Stayed calm and acknowledged the frustration", "hint": "Empathy before explanation.", "weight": 2, "critical": True},
                 {"text": "Verified the patient before discussing the account", "hint": "Name and date of birth.", "weight": 1, "critical": False},
                 {"text": "Explained the charge in plain words", "hint": "What it was, what insurance paid, what is left.", "weight": 2, "critical": False},
                 {"text": "Offered at least one option (payment plan, resubmission, itemized statement)", "hint": "Give them a path.", "weight": 2, "critical": True},
                 {"text": "Set a clear next step with a date", "hint": "Who does what by when.", "weight": 2, "critical": True},
                 {"text": "Thanked the caller and confirmed how to reach them", "hint": "Close warm.", "weight": 1, "critical": False}]}},
        ],
    },
    "insurance": {
        "label": "Insurance agency", "business": "agency", "place": "office", "customer": "caller", "trainer": "insurance agency phone coach",
        "offering": {"label": "policy", "plural": "policies", "hint": "Auto and home bundle, 2 cars, 1 house", "field": "Policies or products the caller can mention", "field_help": "'Auto', 'home', 'renters', 'life', 'small business' is plenty."},
        "departments": [
            {"key": "ins_quote", "label": "New quotes", "call": "quote call", "prefix": "Caller:", "rep": "an insurance agent",
             "brief": "an inbound call from someone shopping for a quote (auto, home, bundle); the agent should get the name and number early, learn what they have today and why they are shopping, uncover bundle opportunities, avoid a blind price, and set a quote appointment or collect the info needed to quote",
             "curveballs": ["You just want the cheapest price and say so", "Your current carrier just raised your rate 30 percent", "You have a teen driver about to get licensed", "You had a claim last year", "You are also shopping two other agencies", "You want the quote texted, not a call back"],
             "defaults": ["my auto policy", "an auto and home bundle"],
             "scorecard": {"name": "Quote Call", "criteria": [
                 {"text": "Answered with their name and the agency", "hint": "Name and agency.", "weight": 1, "critical": False},
                 {"text": "Got and used the caller's name", "hint": "Ask early, use it.", "weight": 1, "critical": False},
                 {"text": "Asked what they have today and why they are shopping", "hint": "Current carrier, rate change, life event.", "weight": 2, "critical": False},
                 {"text": "Looked for a bundle or additional coverage opportunity", "hint": "Home, renters, life, umbrella.", "weight": 1, "critical": False},
                 {"text": "Did not quote a price without the needed details", "hint": "Explain what drives the number.", "weight": 2, "critical": True},
                 {"text": "Set a quote appointment or collected the info to quote", "hint": "Two times, or gather drivers/vehicles/address.", "weight": 2, "critical": True},
                 {"text": "Got the caller's phone number and email", "hint": "Repeat back.", "weight": 2, "critical": True},
                 {"text": "Recapped next steps and thanked the caller", "hint": "Who does what by when.", "weight": 1, "critical": False}]}},
            {"key": "ins_service", "label": "Policy service", "call": "policy service call", "prefix": "Policyholder:", "rep": "a customer service rep",
             "brief": "an inbound call from an existing policyholder (billing question, adding a car, a claim, a rate increase); the rep should verify the caller, handle the request completely, review coverage for gaps or discounts, and confirm next steps",
             "curveballs": ["You are upset about a rate increase and thinking of leaving", "You need proof of insurance in the next 10 minutes", "You just bought a car and are on the dealer's lot", "You had an accident and are shaken up", "You want to drop coverage to save money", "You are calling for your spouse who is not on the call"],
             "defaults": ["my auto policy", "my homeowners policy"],
             "scorecard": {"name": "Policy Service Call", "criteria": [
                 {"text": "Answered with their name and the agency", "hint": "Name and agency.", "weight": 1, "critical": False},
                 {"text": "Verified the policyholder", "hint": "Name plus one identifier.", "weight": 1, "critical": False},
                 {"text": "Acknowledged the concern with empathy", "hint": "Especially on rate increases and claims.", "weight": 2, "critical": True},
                 {"text": "Handled the request completely or set a clear owner and time", "hint": "No vague 'someone will call you'.", "weight": 2, "critical": True},
                 {"text": "Reviewed coverage for gaps or discounts", "hint": "One genuine suggestion.", "weight": 1, "critical": False},
                 {"text": "Confirmed the phone number and email", "hint": "Repeat back.", "weight": 1, "critical": False},
                 {"text": "Recapped next steps and thanked the caller", "hint": "Close clear and warm.", "weight": 1, "critical": False}]}},
        ],
    },
    "fitness": {
        "label": "Fitness and studios", "business": "gym", "place": "club", "customer": "caller", "trainer": "fitness membership phone coach",
        "offering": {"label": "membership", "plural": "memberships", "hint": "Unlimited monthly, 6 am HIIT class, personal training intro", "field": "Memberships, classes or programs the caller can mention", "field_help": "'Unlimited monthly', 'yoga 10-pack', '6-week challenge' is plenty."},
        "departments": [
            {"key": "fit_membership", "label": "Membership inquiries", "call": "membership call", "prefix": "Caller:", "rep": "a membership advisor",
             "brief": "an inbound call from someone asking about joining or about pricing; the advisor should get the name and number, learn the goal and why now, avoid leading with price, describe the experience, and book a tour or free first class with two time options",
             "curveballs": ["You only want the monthly price and the joining fee", "You have not worked out in three years and are embarrassed", "You are comparing two other gyms", "You want to know about cancelling before you even join", "You can only come at 5 am", "You ask whether there is childcare"],
             "defaults": ["the unlimited membership", "the intro class special"],
             "scorecard": {"name": "Membership Inquiry Call", "criteria": [
                 {"text": "Answered with their name and the club", "hint": "Name and club, upbeat.", "weight": 1, "critical": False},
                 {"text": "Got and used the caller's name", "hint": "Ask early, use it.", "weight": 1, "critical": False},
                 {"text": "Asked about their goal and why now", "hint": "Listen for the real reason.", "weight": 2, "critical": False},
                 {"text": "Handled the price question without leading with price", "hint": "Answer honestly, tie it to the goal.", "weight": 2, "critical": True},
                 {"text": "Invited them to a tour or free first class with two time options", "hint": "'Tonight at 6 or Saturday at 9?'", "weight": 2, "critical": True},
                 {"text": "Got the caller's phone number", "hint": "Repeat back.", "weight": 2, "critical": True},
                 {"text": "Recapped and thanked the caller", "hint": "Day, time, what to bring.", "weight": 1, "critical": False}]}},
            {"key": "fit_training", "label": "Training and classes", "call": "training call", "prefix": "Member:", "rep": "a coach",
             "brief": "an inbound call asking about personal training, classes or a program; the coach should learn the goal and experience level, explain the program plainly, mention pricing honestly, and book an assessment or first session",
             "curveballs": ["You had a bad experience with a trainer before", "You ask whether the trainer is certified", "You want results for a wedding in 8 weeks", "You have a bad knee", "You want to bring a friend", "You ask if there is a trial session"],
             "defaults": ["personal training", "the 6-week challenge"],
             "scorecard": {"name": "Training Inquiry Call", "criteria": [
                 {"text": "Answered with their name and the club", "hint": "Name and club.", "weight": 1, "critical": False},
                 {"text": "Got and used the caller's name", "hint": "Ask early, use it.", "weight": 1, "critical": False},
                 {"text": "Asked about the goal, experience and any limitations", "hint": "Goal, history, injuries.", "weight": 2, "critical": False},
                 {"text": "Explained the program or training clearly", "hint": "What a session looks like.", "weight": 1, "critical": False},
                 {"text": "Discussed pricing honestly when asked", "hint": "Say the number, tie it to the goal.", "weight": 1, "critical": False},
                 {"text": "Booked an assessment or first session with two time options", "hint": "Two choices, then confirm.", "weight": 2, "critical": True},
                 {"text": "Got the caller's phone number", "hint": "Repeat back.", "weight": 2, "critical": True},
                 {"text": "Recapped and thanked the caller", "hint": "Close warm.", "weight": 1, "critical": False}]}},
            {"key": "fit_retention", "label": "Cancel and freeze", "call": "cancellation call", "prefix": "Member:", "rep": "a member services rep",
             "brief": "an inbound call from a member who wants to cancel or freeze; the rep should listen without pushing, learn the real reason, offer a fitting alternative (freeze, downgrade, schedule change, a session with a coach) once, and if they still want to cancel, make it easy and leave the door open",
             "curveballs": ["You are moving out of state", "You have not been in two months and feel guilty", "You found a cheaper gym", "You are mad about a charge you did not expect", "You had surgery and cannot work out for 3 months", "You just want it done, no sales pitch"],
             "defaults": ["my membership", "my monthly plan"],
             "scorecard": {"name": "Cancel or Freeze Call", "criteria": [
                 {"text": "Answered with their name and the club", "hint": "Name and club.", "weight": 1, "critical": False},
                 {"text": "Listened and acknowledged without pushing back immediately", "hint": "Let them finish.", "weight": 2, "critical": True},
                 {"text": "Learned the real reason", "hint": "One open question.", "weight": 2, "critical": False},
                 {"text": "Offered one fitting alternative (freeze, downgrade, coach session)", "hint": "Once, matched to the reason.", "weight": 2, "critical": True},
                 {"text": "Made the cancellation easy if they still wanted it", "hint": "No hoops.", "weight": 2, "critical": True},
                 {"text": "Left the door open warmly", "hint": "'We'd love to have you back.'", "weight": 1, "critical": False},
                 {"text": "Confirmed what happens next and when", "hint": "Last charge date, confirmation email.", "weight": 1, "critical": False}]}},
        ],
    },
    "property_management": {
        "label": "Apartment leasing", "business": "community", "place": "leasing office", "customer": "prospect", "trainer": "leasing phone coach",
        "offering": {"label": "floor plan", "plural": "floor plans", "hint": "2 bed 2 bath, 3rd floor, 1,850 a month", "field": "Floor plans or units the caller can mention", "field_help": "'2x2 at 1,850', '1 bed with garage' is plenty."},
        "departments": [
            {"key": "pm_leasing", "label": "Leasing inquiries", "call": "leasing call", "prefix": "Prospect:", "rep": "a leasing consultant",
             "brief": "an inbound call from a prospect asking about availability and pricing; the consultant should get the name and number, learn move-in date, budget and must-haves, describe the community beyond the price, and set a tour with two time options",
             "curveballs": ["You only want the price of a 2 bedroom and the specials", "You need to move in two weeks", "You have a large dog", "Your credit is not great and you ask what they check", "You are touring three other communities this weekend", "You want a virtual tour instead"],
             "defaults": ["the 2 bedroom you have listed", "the 1 bedroom with the garage"],
             "scorecard": {"name": "Leasing Inquiry Call", "criteria": [
                 {"text": "Answered with their name and the community", "hint": "Name and community, upbeat.", "weight": 1, "critical": False},
                 {"text": "Got and used the caller's name", "hint": "Ask early, use it.", "weight": 1, "critical": False},
                 {"text": "Asked about move-in date, budget and must-haves", "hint": "Three quick questions.", "weight": 2, "critical": False},
                 {"text": "Described the community beyond price", "hint": "Two features that match what they said.", "weight": 1, "critical": False},
                 {"text": "Answered availability and pricing honestly", "hint": "Real numbers or a clear 'let me check'.", "weight": 1, "critical": False},
                 {"text": "Set a tour with two time options", "hint": "'Today at 4 or tomorrow at 11?'", "weight": 2, "critical": True},
                 {"text": "Got the caller's phone number and email", "hint": "Repeat back.", "weight": 2, "critical": True},
                 {"text": "Recapped and thanked the caller", "hint": "Day, time, what to bring.", "weight": 1, "critical": False}]}},
            {"key": "pm_resident", "label": "Resident service", "call": "resident call", "prefix": "Resident:", "rep": "a community assistant",
             "brief": "an inbound call from a current resident (maintenance request, noise complaint, renewal question, payment issue); the assistant should verify the resident, show empathy, log or handle the request completely, set a clear expectation and follow-up time, and confirm contact details",
             "curveballs": ["Your AC has been out for two days and nobody called back", "You are upset about a renewal increase", "You lost your key at 9 pm", "Your neighbor is loud every night", "You want to break your lease", "You are calling for your roommate"],
             "defaults": ["my apartment", "my renewal"],
             "scorecard": {"name": "Resident Service Call", "criteria": [
                 {"text": "Answered with their name and the community", "hint": "Name and community.", "weight": 1, "critical": False},
                 {"text": "Verified the resident and the unit", "hint": "Name and unit number.", "weight": 1, "critical": False},
                 {"text": "Acknowledged the concern with empathy", "hint": "Before explaining anything.", "weight": 2, "critical": True},
                 {"text": "Handled or logged the request completely", "hint": "Work order number or a clear owner.", "weight": 2, "critical": True},
                 {"text": "Set a clear expectation and follow-up time", "hint": "When and how they will hear back.", "weight": 2, "critical": True},
                 {"text": "Confirmed the phone number", "hint": "Repeat back.", "weight": 1, "critical": False},
                 {"text": "Thanked the resident and closed warmly", "hint": "Leave them feeling heard.", "weight": 1, "critical": False}]}},
        ],
    },
    "general": {
        "label": "General business", "business": "business", "place": "office", "customer": "caller", "trainer": "phone skills coach",
        "offering": {"label": "product or service", "plural": "products or services", "hint": "the spring special you have on your website", "field": "Products or services the caller can mention", "field_help": "Real offers, packages or services make the calls believable. A name and a price is plenty."},
        "departments": [
            {"key": "gen_inquiry", "label": "New inquiries", "call": "inquiry call", "prefix": "Caller:", "rep": "a team member",
             "brief": "an inbound call from a prospective customer asking about a product or service; the team member should greet warmly, get the name and number, understand what the caller needs and why now, answer clearly without overpromising, and propose a concrete next step with two time options",
             "curveballs": ["You are comparing two other companies and say so", "You want a price before you will share anything else", "You only have a couple of minutes", "You had a bad experience with a competitor and are skeptical", "Someone else makes the final decision", "You ask if there is any discount"],
             "defaults": ["the special you have on your website", "the package you advertise"],
             "scorecard": {"name": "New Inquiry Call", "criteria": [
                 {"text": "Answered with their name and the business", "hint": "Name and company, warm and unhurried.", "weight": 1, "critical": False},
                 {"text": "Got and used the caller's name", "hint": "Ask early, use it twice.", "weight": 1, "critical": False},
                 {"text": "Asked what the caller needs and why now", "hint": "Open question before any pitch.", "weight": 2, "critical": False},
                 {"text": "Answered clearly and honestly", "hint": "Real information or a clear 'let me find out'.", "weight": 1, "critical": False},
                 {"text": "Proposed a next step with two time options", "hint": "'Today at 4 or tomorrow at 10?'", "weight": 2, "critical": True},
                 {"text": "Got the caller's phone number", "hint": "Best number in case you get disconnected.", "weight": 2, "critical": True},
                 {"text": "Recapped and thanked the caller", "hint": "Who does what next, then a genuine thank you.", "weight": 1, "critical": False}]}},
            {"key": "gen_support", "label": "Existing customers", "call": "customer service call", "prefix": "Customer:", "rep": "a customer service rep",
             "brief": "an inbound call from a current customer with a problem, question or complaint; the rep should verify the customer, acknowledge the concern with empathy, resolve or log it completely, set a clear expectation and follow-up time, and confirm contact details",
             "curveballs": ["You have already called twice and nobody called back", "You want to speak to a manager right away", "You are calling on behalf of a family member", "You want a refund and say so up front", "You are polite but clearly frustrated", "You are not sure of your account details"],
             "defaults": ["my account", "my last order"],
             "scorecard": {"name": "Customer Service Call", "criteria": [
                 {"text": "Answered with their name and the business", "hint": "Name and company.", "weight": 1, "critical": False},
                 {"text": "Verified the customer", "hint": "Name and account or order.", "weight": 1, "critical": False},
                 {"text": "Acknowledged the concern with empathy", "hint": "Before explaining anything.", "weight": 2, "critical": True},
                 {"text": "Resolved or logged the request completely", "hint": "A fix, a ticket number or a clear owner.", "weight": 2, "critical": True},
                 {"text": "Set a clear expectation and follow-up time", "hint": "When and how they will hear back.", "weight": 2, "critical": True},
                 {"text": "Confirmed the phone number", "hint": "Repeat back.", "weight": 1, "critical": False},
                 {"text": "Thanked the customer and closed warmly", "hint": "Leave them feeling heard.", "weight": 1, "critical": False}]}},
        ],
    },
}

_DEPT_INDEX = {d["key"]: (ik, d) for ik, ind in INDUSTRIES.items() for d in ind["departments"]}

# Free-text store industries (setup wizard labels, old values, whatever a manager typed) -> a pack key.
_LABEL_HINTS = [
    ("automotive", ("auto", "dealer", "car ", "cars", "motor", "powersport", "rv ", "marine", "boat")),
    ("real_estate", ("real estate", "realty", "realtor", "broker", "mortgage")),
    ("home_services", ("home service", "hvac", "plumb", "roof", "electric", "landscap", "pest", "clean", "contractor", "remodel", "solar", "garage")),
    ("medical_dental", ("medical", "dental", "dentist", "health", "wellness", "clinic", "chiro", "ortho", "derm", "vet", "optom", "physical therapy", "med spa", "medspa")),
    ("insurance", ("insurance", "insur")),
    ("fitness", ("fitness", "gym", "crossfit", "yoga", "pilates", "martial")),
    ("property_management", ("apartment", "property", "leasing", "multifamily", "multi-family", "community")),
]


def key_for(value: Optional[str]) -> str:
    """Pack key for any industry value: a pack key, a pack label, or a free-text store industry ('Automotive / Dealership')."""
    v = (value or "").strip().lower()
    if not v:
        return DEFAULT_INDUSTRY
    if v in INDUSTRIES:
        return v
    for k, pack in INDUSTRIES.items():
        if v == pack["label"].lower():
            return k
    for k, hints in _LABEL_HINTS:
        if any(h in v for h in hints):
            return k
    return "general"


async def store_industry(db, store_id) -> str:
    """The pack a SaaS store (org) runs on, from stores.industry. Missing store or blank industry = automotive (the original product)."""
    from bson import ObjectId
    if not store_id or not ObjectId.is_valid(str(store_id)):
        return DEFAULT_INDUSTRY
    s = await db.stores.find_one({"_id": ObjectId(str(store_id))}, {"industry": 1})
    return key_for((s or {}).get("industry"))


def get(key: Optional[str]) -> dict:
    return INDUSTRIES.get(key or "") or INDUSTRIES[DEFAULT_INDUSTRY]


def key_of(obj: Optional[dict]) -> str:
    k = (obj or {}).get("industry")
    return k if k in INDUSTRIES else DEFAULT_INDUSTRY


def departments(industry_key: Optional[str]) -> list:
    return get(industry_key)["departments"]


def dept_keys(industry_key: Optional[str]) -> list:
    return [d["key"] for d in departments(industry_key)]


def all_dept_keys() -> list:
    return list(_DEPT_INDEX.keys())


def dept(dept_key: Optional[str], industry_key: Optional[str] = None) -> dict:
    """Department pack by key; falls back to the industry's first department."""
    hit = _DEPT_INDEX.get(dept_key or "")
    if hit and (industry_key is None or hit[0] == industry_key or industry_key not in INDUSTRIES):
        return hit[1]
    return departments(industry_key)[0]


def industry_of_dept(dept_key: Optional[str]) -> str:
    hit = _DEPT_INDEX.get(dept_key or "")
    return hit[0] if hit else DEFAULT_INDUSTRY


def dept_label(dept_key: Optional[str]) -> str:
    hit = _DEPT_INDEX.get(dept_key or "")
    return hit[1]["label"] if hit else (dept_key or "").replace("_", " ").title() or "Sales"


def dept_options(industry_key: Optional[str]) -> list:
    return [{"key": d["key"], "label": d["label"], "call": d["call"], "rep": d["rep"]} for d in departments(industry_key)]


def label_map() -> dict:
    return {k: d["label"] for k, (_, d) in _DEPT_INDEX.items()}


def for_api() -> list:
    out = []
    for k, ind in INDUSTRIES.items():
        out.append({"key": k, "label": ind["label"], "business": ind["business"], "place": ind["place"], "customer": ind["customer"],
                    "offering": ind["offering"], "departments": [{"key": d["key"], "label": d["label"], "call": d["call"], "rep": d["rep"]} for d in ind["departments"]]})
    return out


def fill_offering(text, offering: str, place: str):
    """{vehicle} is the legacy placeholder from the automotive content; {offering} means the same thing everywhere."""
    if isinstance(text, list):
        return [fill_offering(x, offering, place) for x in text]
    if not isinstance(text, str):
        return text
    return text.replace("{vehicle}", offering).replace("{offering}", offering).replace("{store}", place)



# ---------------------------------------------------------------- the rep's VA (customer-facing texting assistant) per industry
# safe = what the VA may handle itself; hold = always goes to the rep; hold_words = whole-phrase triggers that pause the VA
# (merged with VA_BASE_HOLD_WORDS); slot = the one personal interview topic that changes per industry (field, what Jessi asks, label).
VA_BASE_HOLD_WORDS = ["in stock", "available", "availability", "do you have", "do you stock", "price", "pricing", "cost", "how much", "what does it cost",
                      "what's the price", "quote", "estimate", "discount", "fee", "fees", "refund", "cancel", "warranty", "guarantee", "how long will it take"]
VA_BASE_SAFE = ["a warm, human reply to whatever they said (thanks, small talk, good news, a photo they sent)", "confirming you got their message and that you are on it",
                "hours, address and directions when they are in FACTS", "helping them pick a time to come in or talk (the exact time gets confirmed by you personally)"]
VA_BASE_HOLD = ["any price, quote, payment, fee, discount or refund", "whether something specific is available, in stock or possible, unless FACTS or live data in the message say so",
                "policies, contracts, legal or technical specifics not in FACTS", "promises about dates, delivery or outcomes"]
VA = {
    "automotive": {
        "tone": "Straight talk, no dealer-speak, never pushy. You sound like a salesperson who actually likes people.",
        "safe": ["what to bring for a visit, a test drive or a trade appraisal (license, insurance, title or payoff, both keys)", "a quick thank-you after a visit, a purchase or a service appointment"],
        "hold": ["price, out-the-door numbers, monthly payments, APR, lease terms, rebates or discounts", "trade-in values", "whether a specific vehicle is on the lot, unless LIVE INVENTORY is in the message",
                 "warranty, recall or repair coverage", "credit approval or financing options"],
        "hold_words": ["trade", "trade-in", "trade in", "trade value", "finance", "financing", "payment", "monthly", "apr", "interest rate", "lease", "vin", "which one", "which ones",
                       "what models", "which model", "what trim", "trim", "mileage", "how many miles", "msrp", "out the door", "down payment", "what color", "what colour", "which color",
                       "which colour", "color name", "colour name", "do you have it in", "does it come", "recall", "approved", "credit", "rebate"],
        "finance_words": ["trade", "trade-in", "trade in", "trade value", "finance", "financing", "payment", "monthly", "apr", "interest rate", "lease", "down payment", "out the door"],
        "slot": ("vehicles", "What they drive and their dream vehicle", "What you drive"),
        "scenarios": [("New Lead", "flash", "Hey, I saw your dealership online and I'm interested in trading in my truck. What does that process look like?"),
                      ("Price Ask", "pricetag", "What's the best price you can do on the white Tahoe? And what would the payment be?"),
                      ("Happy Customer", "happy", "Just wanted to say I love the car! Everyone keeps asking about it. You guys were amazing."),
                      ("Set a Time", "calendar", "Could I come see it tomorrow after work, around 5:30?")],
    },
    "real_estate": {
        "tone": "Warm, local, unhurried. You know the area and you care where they end up living.",
        "safe": ["what to expect at a showing and what to bring", "a quick thank-you after a showing or a closing"],
        "hold": ["list price, what a seller will take, offers, counteroffers or commission", "whether a listing is still available, pending or under contract", "mortgage rates, pre-approval, closing costs, HOA fees or taxes",
                 "square footage, lot size, year built or any spec not in FACTS", "anything about the contract, disclosures or inspections"],
        "hold_words": ["offer", "asking", "listed at", "list price", "still available", "under contract", "pending", "closing", "closing costs", "hoa", "square feet", "sq ft", "sqft",
                       "lot size", "year built", "commission", "mortgage", "rate", "pre-approved", "preapproved", "pre-approval", "inspection", "appraisal", "earnest", "taxes"],
        "finance_words": [],
        "slot": ("interests", "The neighborhood they live in and what they love about the area", "Your neighborhood"),
        "scenarios": [("New Buyer", "flash", "Hi, I saw the house on Maple Street online. Is it still available and what's the asking price?"),
                      ("Seller", "home", "Thinking about selling next spring. What do you think my place would go for?"),
                      ("Happy Client", "happy", "We're all moved in and the kids love the yard. Thank you for everything!"),
                      ("Showing", "calendar", "Could we see it Saturday morning?")],
    },
    "home_services": {
        "tone": "Practical, friendly, reassuring. You sound like the person who actually shows up on time.",
        "safe": ["what to have ready before a visit (access, photos of the problem, model numbers)", "a quick thank-you after a job"],
        "hold": ["prices, estimates, quotes, hourly rates or what a job will run", "how long a job takes or when a crew can be there", "whether something is covered by warranty or insurance",
                 "diagnosing the problem from a description"],
        "hold_words": ["rate", "hourly", "when can you", "when could you", "covered", "insurance", "permit", "emergency", "same day", "what's wrong", "diagnos", "fix it today"],
        "finance_words": [],
        "slot": ("interests", "A job or project they are proud of and what they like about the trade", "Work you are proud of"),
        "scenarios": [("New Request", "flash", "Hi, our AC stopped cooling last night. Can someone come out this week and what would it cost?"),
                      ("Follow-Up", "refresh-circle", "Hey, just checking if you got the photos I sent of the water heater."),
                      ("Happy Customer", "happy", "The crew was great today, everything works perfect. Thank you!"),
                      ("Set a Time", "calendar", "Does Thursday afternoon work for the estimate?")],
    },
    "medical_dental": {
        "tone": "Calm, kind and precise. Never clinical advice, never alarm, never guess.",
        "safe": ["what to bring to an appointment (insurance card, ID, current medications list)", "confirming they got a message or a form", "a quick thank-you after a visit"],
        "hold": ["anything medical: symptoms, whether something is normal, diagnoses, medications, dosages or test results", "insurance coverage, copays, costs or billing",
                 "prescription refills", "anything urgent (tell them to call the office line or 911 right now)"],
        "hold_words": ["copay", "co-pay", "deductible", "covered", "coverage", "insurance", "bill", "billing", "results", "prescription", "refill", "medication", "dose", "symptom",
                       "pain", "swelling", "bleeding", "infection", "diagnos", "is this normal", "emergency", "urgent"],
        "finance_words": [],
        "slot": ("interests", "What they love about caring for patients", "Why you love this work"),
        "scenarios": [("New Patient", "flash", "Hi, are you taking new patients? I need a cleaning and I think I have a cavity."),
                      ("Question", "help-circle", "My tooth is still sore two days after the filling, is that normal?"),
                      ("Happy Patient", "happy", "Thanks again for fitting me in yesterday, feeling so much better."),
                      ("Reschedule", "calendar", "Can I move my appointment to Friday morning?")],
    },
    "insurance": {
        "tone": "Clear, steady and trustworthy. You explain, you never sell fear.",
        "safe": ["what information to gather for a review (current policy, vehicles, drivers, home details)", "confirming documents or photos arrived"],
        "hold": ["premiums, quotes, rates or discounts", "what a policy covers or excludes, deductibles or limits", "claims: status, whether it is covered, who is at fault",
                 "how much coverage someone needs", "binding, changing or cancelling coverage"],
        "hold_words": ["premium", "rate", "deductible", "covered", "coverage", "claim", "exclusion", "bind", "renewal", "liability", "full coverage", "how much coverage", "at fault", "policy"],
        "finance_words": [],
        "slot": ("interests", "A time they really came through for a client", "A client story"),
        "scenarios": [("New Quote", "flash", "Hi, looking to switch my auto and home. What would you charge for both?"),
                      ("Claim", "shield", "Someone backed into me in a parking lot. Am I covered and what happens to my rate?"),
                      ("Happy Client", "happy", "Thanks for walking my mom through her policy, she felt so much better."),
                      ("Review", "calendar", "Can we do a policy review call next week?")],
    },
    "fitness": {
        "tone": "Upbeat, encouraging, real. Never preachy.",
        "safe": ["what to bring or wear for a first visit", "confirming they are booked (the exact time gets confirmed by you)", "cheering on a win they share"],
        "hold": ["membership prices, promotions, contracts, cancellations or freezes", "medical, injury or diet advice", "guarantees about results", "billing disputes"],
        "hold_words": ["membership", "rate", "promo", "freeze", "contract", "billing", "charged", "injur", "diet", "results", "lose", "pounds", "how many calories"],
        "finance_words": [],
        "slot": ("interests", "How they train themselves and what got them into fitness", "Your own training"),
        "scenarios": [("New Lead", "flash", "Hey, what does a membership run and do you have anything for beginners?"),
                      ("Follow-Up", "refresh-circle", "I missed the last two weeks, travel got crazy. Still have a spot for me?"),
                      ("Win", "happy", "Down 12 pounds since March! Couldn't have done it without you."),
                      ("Set a Time", "calendar", "Can I come in for that intro session Tuesday at 6?")],
    },
    "property_management": {
        "tone": "Friendly, organized, quick. You make moving feel easy.",
        "safe": ["what to bring to a tour or to apply (ID, proof of income)", "confirming an application or a maintenance request came in", "a quick thank-you after a tour"],
        "hold": ["rent, deposits, fees, specials or what is negotiable", "whether a specific unit or floor plan is available or the move-in date, unless in FACTS", "application status, approval, credit or income requirements",
                 "lease terms, breaking a lease or pet policy specifics not in FACTS", "maintenance emergencies (give them the emergency line)"],
        "hold_words": ["rent", "deposit", "special", "vacan", "move in", "move-in", "floor plan", "approved", "application", "credit", "income", "lease", "break my lease", "pet",
                       "maintenance", "broken", "leak", "not working", "no heat", "no hot water"],
        "finance_words": [],
        "slot": ("interests", "What they love about the community they manage", "Your community"),
        "scenarios": [("New Prospect", "flash", "Hi, do you have any 2 bedrooms available in June and what's the rent?"),
                      ("Resident", "home", "My kitchen faucet has been dripping for a week, can someone look at it?"),
                      ("Happy Resident", "happy", "Loving the new place, the move went so smooth. Thanks for all your help!"),
                      ("Tour", "calendar", "Could I tour Saturday around noon?")],
    },
    "general": {
        "tone": "Warm, clear and helpful. You sound like a person, not a company.",
        "safe": [],
        "hold": ["availability or delivery dates", "anything about contracts, policies or technical specifics not in FACTS"],
        "hold_words": ["delivery", "ship", "when will", "policy", "contract"],
        "finance_words": [],
        "slot": ("interests", "What they love most about the work", "Why you love this work"),
        "scenarios": [("New Inquiry", "flash", "Hi, I found you online. What do you charge and how soon could you help?"),
                      ("Follow-Up", "refresh-circle", "Hey, just checking in on where things stand."),
                      ("Happy Customer", "happy", "Everything turned out great, thank you so much!"),
                      ("Set a Time", "calendar", "Could we talk tomorrow afternoon?")],
    },
}


def va(key: Optional[str]) -> dict:
    """The VA block for an industry, base lists merged in."""
    k = key if key in VA else "general"
    pack, block = INDUSTRIES[k], VA[k]
    return {"key": k, "label": pack["label"], "business": pack["business"], "customer": pack["customer"], "offering": pack["offering"]["label"], "tone": block["tone"],
            "safe": VA_BASE_SAFE + block["safe"], "hold": block["hold"] + VA_BASE_HOLD, "hold_words": list(dict.fromkeys(VA_BASE_HOLD_WORDS + block["hold_words"])),
            "finance_words": block["finance_words"], "slot": block["slot"], "scenarios": [{"label": l, "icon": i, "message": m} for l, i, m in block["scenarios"]]}


def va_options() -> list:
    return [{"key": k, "label": INDUSTRIES[k]["label"]} for k in VA]


async def va_industry_for(db, user: Optional[dict]) -> dict:
    """Which industry a rep's VA speaks: the store's Industry setting, else what the rep picked in My Profile, else General.
    {key, label, source: store|profile|default, store_name}"""
    from bson import ObjectId
    from services.lead_flows import user_store_id
    sid = user_store_id(user or {}) if user else None
    store = await db.stores.find_one({"_id": ObjectId(str(sid))}, {"industry": 1, "name": 1}) if sid and ObjectId.is_valid(str(sid)) else None
    if store and (store.get("industry") or "").strip():
        k = key_for(store["industry"])
        return {"key": k, "label": INDUSTRIES[k]["label"], "source": "store", "store_name": store.get("name")}
    mine = (user or {}).get("industry")
    if mine in VA:
        return {"key": mine, "label": INDUSTRIES[mine]["label"], "source": "profile", "store_name": (store or {}).get("name")}
    return {"key": "general", "label": INDUSTRIES["general"]["label"], "source": "default", "store_name": (store or {}).get("name")}


# ---------------------------------------------------------------- translations (client-facing words per language)
# Only what a Dutch dealer, GM or rep reads or hears. Admin screens stay English until Phase E.
TRANSLATIONS = {
    "nl": {
        "automotive": {
            "label": "Autobedrijf", "business": "autobedrijf", "place": "het autobedrijf", "customer": "mystery shopper", "trainer": "verkooptrainer voor autobedrijven",
            "offering": {"label": "auto", "plural": "auto's", "hint": "2024 Volkswagen Golf 1.5 eTSI Style", "field": "Auto's die onze shopper mag noemen", "field_help": "Echte auto's uit je voorraad maken de gesprekken geloofwaardig. Bouwjaar, merk, model en uitvoering is genoeg."},
            "departments": {
                "sales": {"label": "Verkoop", "call": "verkoopgesprek", "rep": "een verkoopadviseur", "prefix": "Verkoopbeller:"},
                "service": {"label": "Werkplaats", "call": "servicegesprek", "rep": "een serviceadviseur", "prefix": "Servicebeller:"},
                "parts": {"label": "Onderdelen", "call": "onderdelengesprek", "rep": "een onderdelenadviseur", "prefix": "Onderdelenbeller:"},
                "rental": {"label": "Verhuur", "call": "verhuurgesprek", "rep": "een verhuurmedewerker", "prefix": "Verhuurbeller:"},
                "collision": {"label": "Schadeherstel", "call": "schadegesprek", "rep": "een schade-expert", "prefix": "Schadebeller:"},
            },
        },
    },
}
# UK and Irish dealers: same pack, the trade's own words (sales executive, parts advisor, bodyshop)
TRANSLATIONS["en-GB"] = {
    "automotive": {
        "label": "Car dealership",
        "offering": {"hint": "2024 Volkswagen Golf 1.5 TSI Life", "field_help": "Real cars from the forecourt make the calls believable. Year, make, model and trim is plenty."},
        "departments": {
            "sales": {"rep": "a sales executive"},
            "parts": {"rep": "a parts advisor"},
            "collision": {"label": "Bodyshop", "call": "bodyshop call", "rep": "a bodyshop estimator", "prefix": "Bodyshop caller:"},
        },
    },
}
TRANSLATIONS["en-IE"] = TRANSLATIONS["en-GB"]


def _tr(locale: Optional[str], industry_key: str) -> dict:
    from services import locales as loc
    return (TRANSLATIONS.get(loc.dialect(locale)) or TRANSLATIONS.get(loc.language(locale)) or {}).get(industry_key) or {}


def translated(industry_key: Optional[str], locale: Optional[str]) -> dict:
    """The industry pack with client-facing words swapped for the locale's language (falls back to English per field)."""
    pack = get(industry_key)
    tr = _tr(locale, key_of({"industry": industry_key}) if industry_key in INDUSTRIES else DEFAULT_INDUSTRY)
    if not tr:
        return pack
    out = {**pack, **{k: v for k, v in tr.items() if k not in ("offering", "departments")}}
    out["offering"] = {**pack["offering"], **(tr.get("offering") or {})}
    out["departments"] = [{**d, **(tr.get("departments", {}).get(d["key"]) or {})} for d in pack["departments"]]
    return out


def dept_label_for(dept_key: Optional[str], locale: Optional[str], industry_key: Optional[str] = None) -> str:
    tr = _tr(locale, industry_key or industry_of_dept(dept_key))
    hit = (tr.get("departments") or {}).get(dept_key or "")
    return hit["label"] if hit and hit.get("label") else dept_label(dept_key)


def dept_options_for(industry_key: Optional[str], locale: Optional[str]) -> list:
    return [{"key": d["key"], "label": d["label"], "call": d["call"], "rep": d["rep"]} for d in translated(industry_key, locale)["departments"]]
