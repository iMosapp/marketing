// Client-facing strings for the no-login pages (proposal, kickoff, report, scorecard). Admin screens stay English.
// Missing Dutch keys fall back to English so nothing renders blank. en-GB / en-IE hold only the words a UK or Irish dealer reads differently.
export type Lang = 'en' | 'en-GB' | 'en-IE' | 'nl';

const T: Record<Lang, Record<string, string>> = {
  'en-GB': {
    'prop.next_body': 'Five minutes: your opening hours, a few {plural} our caller can mention, and the names and mobile numbers of the people to shop. No login, and you can come back to it any time.',
    'prop.title_ph': 'Job title (Dealer Principal, Owner)', 'kick.your_title': 'Job title (Dealer Principal, Owner)', 'kick.cell': 'Your mobile (optional)',
    'kick.people_sub': 'Your plan covers {per} shops a month, spread across everyone below. We only ever call the mobile numbers here; nobody gets a text or an email.',
    'kick.incomplete_1': '1 person still needs a name and a full mobile number.', 'kick.incomplete_n': '{n} people still need a name and a full mobile number.',
    'kick.cell_number': 'Mobile number',
    'rep.intro': "Every call below was placed by our AI {customer} to your team member's mobile during your opening hours, recorded, transcribed and graded the same way for everyone. Tap any shop to hear the call and read the coaching, or tap a name to see that person's history across months.",
    'status.canceled': 'Cancelled',
  },
  'en-IE': {},
  en: {
    // proposal
    'prop.kicker': "I'M ON SOCIAL · PROPOSAL", 'prop.title': 'Phone mystery shopping for {client}', 'prop.invalid': 'This proposal link is not valid anymore.',
    'prop.tile.shops': '{dept} shops / month', 'prop.tile.texts': '{dept} text shops / month', 'prop.tile.month': 'per month', 'prop.tile.term': 'initial term', 'prop.tile.term_v': '{n} mo',
    'prop.signed': 'Signed', 'prop.signed_by': 'Signed by {name}',
    'prop.invoice': 'Your first invoice for {amount} is on its way to {email}. You can pay it right now by card or bank transfer, and the shops begin as soon as it clears.',
    'prop.paid': 'Paid, thank you', 'prop.pay': 'Pay {amount} now', 'prop.thanks': 'Thank you. {sender} will send your first invoice shortly.', 'prop.we': 'We',
    'prop.next': 'Next: tell us who to shop', 'prop.next_body': 'Five minutes: your business hours, a few {plural} our caller can mention, and the names and cell numbers of the people to shop. No login, and you can come back to it any time.',
    'prop.setup': 'Set up your {business} now', 'prop.sign_title': 'Sign to get started', 'prop.name': 'Your full name', 'prop.title_ph': 'Title (GM, Owner)', 'prop.email': 'Email for the invoice and report',
    'prop.esign': 'ELECTRONIC SIGNATURE', 'prop.agree': "I have authority to sign for {client} and agree to the terms above, including recording and evaluating our staff's business calls.",
    'prop.signing': 'Signing…', 'prop.submit': 'Sign and send my first invoice', 'prop.error': 'Something went wrong, try again', 'prop.prepared': 'Prepared by {sender}',
    // kickoff
    'kick.kicker': "I'M ON SOCIAL · STORE SETUP", 'kick.invalid': "This setup link is not valid anymore. Ask I'm On Social for a fresh one.", 'kick.title': 'Set up {name}',
    'kick.intro': 'Takes about five minutes. {sender} gets it the moment you save, and your shops start right away. Come back to this same link any time to add or fix people.',
    'kick.saved': 'Saved, thank you', 'kick.saved_body': '{people} people to shop{added}, {n} {offering}, hours set. {sender} has been notified. You can keep editing below.', 'kick.saved_added': ' ({n} new)',
    'kick.contact': 'Who we send reports to', 'kick.contact_sub': 'The monthly report and invoice go here.', 'kick.your_name': 'Your name', 'kick.your_title': 'Title (GM, Owner)', 'kick.email': 'Email', 'kick.cell': 'Your cell (optional)',
    'kick.hours': 'When we may call', 'kick.hours_sub': 'Shops land at random times inside this window so nobody can predict them.',
    'kick.add': 'Add', 'kick.no_vehicles': 'None yet. Our {customer} will keep it generic until you add some.',
    'kick.people': 'People to shop', 'kick.people_sub': 'Your plan covers {per} shops a month, spread across everyone below. We only ever call the cell numbers here; nobody gets a text or an email.',
    'kick.incomplete_1': '1 person still needs a name and a full cell number.', 'kick.incomplete_n': '{n} people still need a name and a full cell number.',
    'kick.save': 'Save changes', 'kick.start': 'Save and start the shops', 'kick.footer': 'Questions? Reply to the email this link came in.', 'kick.error': 'Something went wrong, try again',
    'kick.days': 'DAYS WE MAY CALL', 'kick.earliest': 'EARLIEST CALL', 'kick.latest': 'LATEST CALL', 'kick.tz': 'YOUR TIME ZONE', 'kick.no_days': 'no days yet',
    'kick.hours_line': 'Our {customer} calls {days}, between {start} and {end} {tz} time, never all at once.',
    'kick.full_name': 'Full name', 'kick.cell_number': 'Cell number', 'kick.title_hint': 'Title ({rep})', 'kick.move_to': 'Move to {dept}', 'kick.add_person': 'Add a {dept} person',
    // report
    'rep.kicker': "I'M ON SOCIAL · MYSTERY SHOP REPORT", 'rep.invalid': "This report link is not valid anymore. Ask I'm On Social for a fresh one.", 'rep.report': 'Report',
    'rep.intro': "Every call below was placed by our AI {customer} to your team member's cell during your business hours, recorded, transcribed and graded the same way for everyone. Tap any shop to hear the call and read the coaching, or tap a name to see that person's history across months.",
    'rep.footer': "Prepared by I'm On Social · imonsocial.com · Questions? Reply to the email this link came in.",
    'rep.all_depts': 'All departments', 'rep.everyone': 'Everyone', 'rep.show_all': 'Show everything',
    'rep.completed': 'Shops completed', 'rep.of': '{a} of {b}', 'rep.avg': 'Average score', 'rep.avg_of': "{name}'s average", 'rep.store_avg': '{who} average', 'rep.store': 'Store', 'rep.people': 'People shopped', 'rep.need': 'Need training',
    'rep.compare': '{name} is {n} point{s} {dir} the {who} line{exact}', 'rep.above': 'above', 'rep.below': 'below', 'rep.exact': ' (right on it)',
    'rep.done': '{n} done', 'rep.coming': '{n} coming', 'rep.unreachable_n': '{n} unreachable', 'rep.avg_short': 'Avg {v}%', 'rep.no_scores': 'No scores yet',
    'rep.leaderboard': '{dept} LEADERBOARD', 'rep.shops_1': '1 shop', 'rep.shops_n': '{n} shops', 'rep.best': 'best {v}%', 'rep.vs': '{d} vs {prev}', 'rep.last_month': 'last month', 'rep.new': 'new this month',
    'rep.who': 'WHO DID WELL, WHO NEEDS ANOTHER LOOK', 'rep.this_month': '{name} THIS MONTH', 'rep.no_match': 'No shops match this filter.', 'rep.nobody': 'No one has been shopped this month yet.', 'rep.history': 'history',
    'rep.crit_1': '1 critical miss', 'rep.crit_n': '{n} critical misses', 'rep.vs_dept': '{d} VS {dept}', 'rep.needs_training': 'NEEDS TRAINING', 'rep.on_line': 'ON THE LINE', 'rep.on_track': 'ON TRACK', 'rep.unreachable': 'UNREACHABLE', 'rep.scheduled': 'SCHEDULED',
    'rep.coach_on': 'Coach on: {items}', 'rep.misses': 'WHAT {who} MISSES MOST', 'rep.misses_team': 'WHAT THE WHOLE TEAM MISSES MOST', 'rep.themes_dept': 'COACHING THEMES FOR THE NEXT {who} MEETING', 'rep.themes': 'COACHING THEMES FOR THE NEXT MEETING', 'rep.coach_who': 'COACH {who} ON',
    'rep.critical': ' (critical)', 'rep.x_of_y': '{a} of {b}', 'rep.matching': 'MATCHING SHOPS', 'rep.every': 'EVERY SHOP', 'rep.completed_n': '{n} COMPLETED', 'rep.inside': 'Recording, transcript and coaching inside',
    // call sheet
    'call.title': 'Shop call', 'call.load_error': 'Could not load this call.', 'call.score': 'score', 'call.tries': '{n} tries', 'call.graded_with': 'Graded with {name}', 'call.script': 'script {v}%', 'call.curveballs': 'Curveballs: {items}',
    'call.crit': 'CRITICAL MISSES', 'call.coaching': 'COACHING', 'call.wins': 'WHAT WENT WELL', 'call.scorecard': 'SCORECARD', 'call.transcript': 'TRANSCRIPT', 'call.rep': 'REP',
    'status.scheduled': 'Scheduled', 'status.dialing': 'Calling now', 'status.live': 'On the call', 'status.grading': 'Grading', 'status.completed': 'Done', 'status.unreachable': 'Unreachable', 'status.failed': 'Failed', 'status.canceled': 'Canceled', 'status.abandoned': 'Hung up',
    'status.texting': 'Texting', 'status.ending': 'Wrapping up', 'tx.badge': 'TEXT SHOP', 'tx.first': 'First reply {d}', 'tx.slowest': 'slowest {d}', 'tx.replies': '{n} replies', 'tx.noreply': 'Never replied', 'tx.after': 'replied after {d}', 'tx.within': 'replied within a minute',
    'sc.thread': 'THE THREAD', 'sc.text_speed': 'Reply speed', 'rep.text_reply': 'First text reply', 'rep.text_noreply': '{n} unanswered', 'rep.texted': 'texted',
    // person sheet
    'per.title': 'Rep', 'per.error': 'Could not load this person right now.', 'per.since': 'shopped since {when}', 'per.delta': '{d} pts vs the month before',
    'per.shops': 'Shops', 'per.nr': 'n/r', 'per.avg': 'Average', 'per.store_avg': 'Store avg · {n} people', 'per.range': 'Best / worst', 'per.crit': 'Critical misses',
    'per.store_line': 'store average across {n} shops', 'per.dept_line': '{dept} line', 'per.on_line': 'Right on the {what} line', 'per.vs_line': '{d} pts {dir} the {what}',
    'per.shop_1': '1 shop', 'per.shop_n': '{n} shops', 'per.critical_n': '{n} critical', 'per.avg_short': 'Avg {v}%', 'per.line_v': '{dept} line {v}%',
    'per.trend': 'TREND · LAST {n} MONTHS', 'per.store_v': 'store {v}%', 'per.keeps': 'KEEPS COMING UP', 'per.every': 'EVERY SHOP · {n}', 'per.none': 'No completed shops yet.', 'per.shopper': 'shopper {name}',
    'per.critical_list': 'Critical: {items}', 'per.inside': 'Full transcript, recording and coaching',
    // scorecard page
    'sc.kicker': "I'M ON SOCIAL · MYSTERY SHOP SCORECARD", 'sc.invalid': 'This scorecard link is not valid.', 'sc.title': "{name}, here's how that call went", 'sc.title_generic': 'Your mystery shop', 'sc.score': 'score',
    'sc.was': 'the {customer} was {name}', 'sc.listen': 'LISTEN BACK', 'sc.nailed': 'WHAT YOU NAILED', 'sc.tough': 'Tough one. The next call is a clean slate.', 'sc.next': 'WORK ON NEXT', 'sc.must': '  · must-have',
    'sc.nothing_missed': 'Nothing missed on the scorecard. Seriously well done.', 'sc.coaching': 'COACHING',
    'sc.footer': "Graded with the {scorecard} scorecard by I'm On Social. Want to practice this exact call any time? Ask your manager about I'm On Social training.", 'sc.phone': 'phone',
  },
  nl: {
    'prop.kicker': "I'M ON SOCIAL · VOORSTEL", 'prop.title': 'Telefonische mystery shops voor {client}', 'prop.invalid': 'Deze voorstel-link is niet meer geldig.',
    'prop.tile.shops': '{dept} shops / maand', 'prop.tile.texts': '{dept} sms-shops / maand', 'prop.tile.month': 'per maand', 'prop.tile.term': 'eerste termijn', 'prop.tile.term_v': '{n} mnd',
    'prop.signed': 'Ondertekend', 'prop.signed_by': 'Ondertekend door {name}',
    'prop.invoice': 'Je eerste factuur van {amount} is onderweg naar {email}. Je kunt direct betalen met iDEAL, kaart of overboeking; de shops starten zodra de betaling binnen is.',
    'prop.paid': 'Betaald, bedankt', 'prop.pay': 'Betaal nu {amount}', 'prop.thanks': 'Bedankt. {sender} stuurt je eerste factuur binnenkort.', 'prop.we': 'Wij',
    'prop.next': 'Volgende stap: wie mogen we bellen?', 'prop.next_body': "Vijf minuten: jullie openingstijden, een paar {plural} die onze beller kan noemen, en de namen en mobiele nummers van de medewerkers. Zonder inloggen, en je kunt altijd terugkomen.",
    'prop.setup': 'Stel jullie {business} nu in', 'prop.sign_title': 'Onderteken om te starten', 'prop.name': 'Je volledige naam', 'prop.title_ph': 'Functie (directeur, eigenaar)', 'prop.email': 'E-mail voor de factuur en het rapport',
    'prop.esign': 'ELEKTRONISCHE HANDTEKENING', 'prop.agree': 'Ik ben bevoegd om namens {client} te ondertekenen en ga akkoord met bovenstaande voorwaarden, inclusief het opnemen en beoordelen van de zakelijke gesprekken van onze medewerkers.',
    'prop.signing': 'Ondertekenen…', 'prop.submit': 'Onderteken en stuur mijn eerste factuur', 'prop.error': 'Er ging iets mis, probeer het opnieuw', 'prop.prepared': 'Opgesteld door {sender}',
    'kick.kicker': "I'M ON SOCIAL · VESTIGING INSTELLEN", 'kick.invalid': "Deze link is niet meer geldig. Vraag I'm On Social om een nieuwe.", 'kick.title': '{name} instellen',
    'kick.intro': 'Duurt ongeveer vijf minuten. {sender} krijgt het zodra je opslaat en de shops starten direct. Kom altijd terug via deze link om medewerkers toe te voegen of aan te passen.',
    'kick.saved': 'Opgeslagen, bedankt', 'kick.saved_body': "{people} medewerkers om te bellen{added}, {n} {offering}, openingstijden ingesteld. {sender} is op de hoogte. Je kunt hieronder blijven bewerken.", 'kick.saved_added': ' ({n} nieuw)',
    'kick.contact': 'Naar wie sturen we de rapporten?', 'kick.contact_sub': 'Het maandrapport en de factuur gaan hierheen.', 'kick.your_name': 'Je naam', 'kick.your_title': 'Functie (directeur, eigenaar)', 'kick.email': 'E-mail', 'kick.cell': 'Je mobiele nummer (optioneel)',
    'kick.hours': 'Wanneer mogen we bellen?', 'kick.hours_sub': 'Shops vallen op willekeurige momenten binnen dit venster, zodat niemand ze kan voorspellen.',
    'kick.add': 'Toevoegen', 'kick.no_vehicles': "Nog geen. Onze {customer} houdt het algemeen tot je er een paar toevoegt.",
    'kick.people': 'Medewerkers om te bellen', 'kick.people_sub': 'Jullie plan dekt {per} shops per maand, verdeeld over iedereen hieronder. We bellen alleen de mobiele nummers hier; niemand krijgt een sms of e-mail.',
    'kick.incomplete_1': '1 medewerker heeft nog een naam en een volledig mobiel nummer nodig.', 'kick.incomplete_n': '{n} medewerkers hebben nog een naam en een volledig mobiel nummer nodig.',
    'kick.save': 'Wijzigingen opslaan', 'kick.start': 'Opslaan en de shops starten', 'kick.footer': 'Vragen? Beantwoord de e-mail waarin deze link stond.', 'kick.error': 'Er ging iets mis, probeer het opnieuw',
    'kick.days': 'DAGEN WAAROP WE MOGEN BELLEN', 'kick.earliest': 'VROEGSTE GESPREK', 'kick.latest': 'LAATSTE GESPREK', 'kick.tz': 'JULLIE TIJDZONE', 'kick.no_days': 'nog geen dagen',
    'kick.hours_line': 'Onze {customer} belt op {days}, tussen {start} en {end} ({tz}), nooit allemaal tegelijk.',
    'kick.full_name': 'Volledige naam', 'kick.cell_number': 'Mobiel nummer', 'kick.title_hint': 'Functie ({rep})', 'kick.move_to': 'Naar {dept}', 'kick.add_person': '{dept}-medewerker toevoegen',
    'rep.kicker': "I'M ON SOCIAL · MYSTERY SHOP RAPPORT", 'rep.invalid': "Deze rapport-link is niet meer geldig. Vraag I'm On Social om een nieuwe.", 'rep.report': 'Rapport',
    'rep.intro': 'Elk gesprek hieronder is door onze AI-{customer} gevoerd naar het mobiele nummer van jullie medewerker, binnen jullie openingstijden, opgenomen, uitgeschreven en voor iedereen op dezelfde manier beoordeeld. Tik op een shop om het gesprek te horen en de coaching te lezen, of op een naam voor de historie van die medewerker.',
    'rep.footer': "Opgesteld door I'm On Social · imonsocial.com · Vragen? Beantwoord de e-mail waarin deze link stond.",
    'rep.all_depts': 'Alle afdelingen', 'rep.everyone': 'Iedereen', 'rep.show_all': 'Alles tonen',
    'rep.completed': 'Shops afgerond', 'rep.of': '{a} van {b}', 'rep.avg': 'Gemiddelde score', 'rep.avg_of': 'Gemiddelde van {name}', 'rep.store_avg': 'Gemiddelde {who}', 'rep.store': 'vestiging', 'rep.people': 'Medewerkers gebeld', 'rep.need': 'Training nodig',
    'rep.compare': '{name} zit {n} punt{s} {dir} de lijn van {who}{exact}', 'rep.above': 'boven', 'rep.below': 'onder', 'rep.exact': ' (er precies op)',
    'rep.done': '{n} afgerond', 'rep.coming': '{n} gepland', 'rep.unreachable_n': '{n} onbereikbaar', 'rep.avg_short': 'Gem. {v}%', 'rep.no_scores': 'Nog geen scores',
    'rep.leaderboard': 'RANGLIJST {dept}', 'rep.shops_1': '1 shop', 'rep.shops_n': '{n} shops', 'rep.best': 'beste {v}%', 'rep.vs': '{d} t.o.v. {prev}', 'rep.last_month': 'vorige maand', 'rep.new': 'nieuw deze maand',
    'rep.who': 'WIE HET GOED DEED, WIE AANDACHT NODIG HEEFT', 'rep.this_month': '{name} DEZE MAAND', 'rep.no_match': 'Geen shops voor dit filter.', 'rep.nobody': 'Deze maand is er nog niemand gebeld.', 'rep.history': 'historie',
    'rep.crit_1': '1 kritieke misser', 'rep.crit_n': '{n} kritieke missers', 'rep.vs_dept': '{d} T.O.V. {dept}', 'rep.needs_training': 'TRAINING NODIG', 'rep.on_line': 'OP DE LIJN', 'rep.on_track': 'OP KOERS', 'rep.unreachable': 'ONBEREIKBAAR', 'rep.scheduled': 'GEPLAND',
    'rep.coach_on': 'Coach op: {items}', 'rep.misses': 'WAT {who} HET VAAKST MIST', 'rep.misses_team': 'WAT HET HELE TEAM HET VAAKST MIST', 'rep.themes_dept': "COACHINGTHEMA'S VOOR HET VOLGENDE {who}-OVERLEG", 'rep.themes': "COACHINGTHEMA'S VOOR HET VOLGENDE OVERLEG", 'rep.coach_who': 'COACH {who} OP',
    'rep.critical': ' (kritiek)', 'rep.x_of_y': '{a} van {b}', 'rep.matching': 'PASSENDE SHOPS', 'rep.every': 'ALLE SHOPS', 'rep.completed_n': '{n} AFGEROND', 'rep.inside': 'Opname, transcript en coaching binnenin',
    'call.title': 'Shopgesprek', 'call.load_error': 'Dit gesprek kon niet worden geladen.', 'call.score': 'score', 'call.tries': '{n} pogingen', 'call.graded_with': 'Beoordeeld met {name}', 'call.script': 'script {v}%', 'call.curveballs': 'Verrassingen: {items}',
    'call.crit': 'KRITIEKE MISSERS', 'call.coaching': 'COACHING', 'call.wins': 'WAT GOED GING', 'call.scorecard': 'SCOREKAART', 'call.transcript': 'TRANSCRIPT', 'call.rep': 'MEDEWERKER',
    'status.scheduled': 'Gepland', 'status.dialing': 'Belt nu', 'status.live': 'In gesprek', 'status.grading': 'Beoordelen', 'status.completed': 'Klaar', 'status.unreachable': 'Onbereikbaar', 'status.failed': 'Mislukt', 'status.canceled': 'Geannuleerd', 'status.abandoned': 'Opgehangen',
    'status.texting': 'Sms-gesprek', 'status.ending': 'Afronden', 'tx.badge': 'SMS-SHOP', 'tx.first': 'Eerste reactie {d}', 'tx.slowest': 'traagste {d}', 'tx.replies': '{n} reacties', 'tx.noreply': 'Nooit gereageerd', 'tx.after': 'reageerde na {d}', 'tx.within': 'reageerde binnen een minuut',
    'sc.thread': 'HET GESPREK', 'sc.text_speed': 'Reactiesnelheid', 'rep.text_reply': 'Eerste sms-reactie', 'rep.text_noreply': '{n} onbeantwoord', 'rep.texted': 'ge-sms\'t',
    'per.title': 'Medewerker', 'per.error': 'Deze medewerker kon nu niet worden geladen.', 'per.since': 'gebeld sinds {when}', 'per.delta': '{d} pt t.o.v. de maand ervoor',
    'per.shops': 'Shops', 'per.nr': 'n.b.', 'per.avg': 'Gemiddelde', 'per.store_avg': 'Gem. vestiging · {n} medewerkers', 'per.range': 'Beste / slechtste', 'per.crit': 'Kritieke missers',
    'per.store_line': 'het vestigingsgemiddelde over {n} shops', 'per.dept_line': 'lijn van {dept}', 'per.on_line': 'Precies op {what}', 'per.vs_line': '{d} pt {dir} {what}',
    'per.shop_1': '1 shop', 'per.shop_n': '{n} shops', 'per.critical_n': '{n} kritiek', 'per.avg_short': 'Gem. {v}%', 'per.line_v': 'lijn {dept} {v}%',
    'per.trend': 'TREND · LAATSTE {n} MAANDEN', 'per.store_v': 'vestiging {v}%', 'per.keeps': 'KOMT STEEDS TERUG', 'per.every': 'ALLE SHOPS · {n}', 'per.none': 'Nog geen afgeronde shops.', 'per.shopper': 'beller {name}',
    'per.critical_list': 'Kritiek: {items}', 'per.inside': 'Volledig transcript, opname en coaching',
    'sc.kicker': "I'M ON SOCIAL · MYSTERY SHOP SCOREKAART", 'sc.invalid': 'Deze scorekaart-link is niet geldig.', 'sc.title': '{name}, zo ging dat gesprek', 'sc.title_generic': 'Jouw mystery shop', 'sc.score': 'score',
    'sc.was': 'de {customer} was {name}', 'sc.listen': 'LUISTER TERUG', 'sc.nailed': 'WAT JE GOED DEED', 'sc.tough': 'Pittig gesprek. Het volgende begint met een schone lei.', 'sc.next': 'WERK HIERAAN', 'sc.must': '  · must-have',
    'sc.nothing_missed': 'Niets gemist op de scorekaart. Echt goed gedaan.', 'sc.coaching': 'COACHING',
    'sc.footer': "Beoordeeld met de scorekaart {scorecard} door I'm On Social. Wil je dit gesprek oefenen wanneer je wilt? Vraag je manager naar I'm On Social training.", 'sc.phone': 'telefoon',
  },
};

T['en-IE'] = { ...T['en-GB'] };

export const langOf = (v?: string | null): Lang => { const s = v || ''; if (s.startsWith('nl')) return 'nl'; if (s === 'en-GB' || s === 'en-IE') return s; return 'en'; };

// tr('rep.of', { a: 3, b: 5 }) -> "3 van 5". Unknown keys return the key so a typo is visible, never blank.
export const makeT = (lang?: Lang | string | null) => {
  const l = langOf(lang as string);
  return (key: string, vars?: Record<string, string | number | null | undefined>) => {
    let s = T[l][key] ?? T.en[key] ?? key;
    for (const [k, v] of Object.entries(vars || {})) s = s.split(`{${k}}`).join(v == null ? '' : String(v));
    return s;
  };
};
export type Tr = ReturnType<typeof makeT>;

const INTL: Record<Lang, string> = { en: 'en-US', 'en-GB': 'en-GB', 'en-IE': 'en-IE', nl: 'nl-NL' };
const EN_DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
export const DAYS_L: Record<Lang, string[]> = { en: EN_DAYS, 'en-GB': EN_DAYS, 'en-IE': EN_DAYS, nl: ['ma', 'di', 'wo', 'do', 'vr', 'za', 'zo'] };
export const daysOf = (lang?: Lang | string | null) => DAYS_L[langOf(lang as string)];

// "9 AM" / "9:30 PM" for English, "09:00" / "21:30" for Dutch (24h clock)
export const fmtHourL = (hm: string, lang?: Lang | string | null) => {
  const [h, m] = (hm || '09:00').split(':').map(Number);
  if (langOf(lang as string) === 'nl') return `${String(h).padStart(2, '0')}:${String(m || 0).padStart(2, '0')}`;
  const ap = h >= 12 ? 'PM' : 'AM'; const hh = h % 12 || 12;
  return m ? `${hh}:${String(m).padStart(2, '0')} ${ap}` : `${hh} ${ap}`;
};
export const fmtWhenL = (iso?: string | null, lang?: Lang | string | null) => (iso ? new Date(iso).toLocaleString(INTL[langOf(lang as string)], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: langOf(lang as string) !== 'nl' }) : '');
export const monthLabelL = (key: string, lang?: Lang | string | null) => { const [y, m] = key.split('-').map(Number); const s = new Date(y, m - 1, 1).toLocaleDateString(INTL[langOf(lang as string)], { month: 'long', year: 'numeric' }); return s.charAt(0).toUpperCase() + s.slice(1); };
export const shortMonthYearL = (iso: string, lang?: Lang | string | null) => new Date(iso).toLocaleDateString(INTL[langOf(lang as string)], { month: 'short', year: 'numeric' });
// "€ 450" the Dutch way, "$450" / "£450" otherwise
export const moneyL = (n?: number | null, currency?: string | null, lang?: Lang | string | null) => {
  const sym = { usd: '$', gbp: '£', eur: '€' }[(currency || 'usd').toLowerCase()] || '$';
  const v = Math.round(n || 0);
  return langOf(lang as string) === 'nl' ? `${sym} ${v.toLocaleString('nl-NL')}` : `${sym}${v.toLocaleString('en-US')}`;
};
