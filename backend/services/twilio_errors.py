"""Plain-English meaning of a text message's delivery state and Twilio error code, for reps and admins."""
from datetime import datetime
from typing import Optional

# code -> (title, what happened, what to do)
CODES = {
    "30003": ("Phone unreachable", "The customer's phone was off or out of service when the carrier tried to deliver.", "Try again in a bit, or call them."),
    "30004": ("Blocked by the customer's carrier or phone", "Their carrier or a blocking app on their phone rejected the message.", "Ask them to check their blocked numbers, or call."),
    "30005": ("Unknown number", "The carrier says this number does not exist or is no longer active.", "Double-check the number with the customer."),
    "30006": ("Landline or unsupported carrier", "This number cannot receive text messages.", "Call instead, or ask for a mobile number."),
    "30007": ("Filtered by the carrier", "The carrier's spam filter blocked this message. Links, attachments and salesy wording trigger it most.", "Resend as plain text with fewer links, or have the customer text you first."),
    "30008": ("Delivery failed", "The carrier rejected the message without saying why. Attachments (photos, contact cards) are the usual cause.", "Resend as plain text."),
    "30019": ("Message too large", "The attachment or text is bigger than the carrier accepts.", "Resend as plain text or with a smaller photo."),
    "30022": ("Sending too fast", "US carriers throttled this number for sending too many messages too quickly.", "Wait a few minutes and resend."),
    "30023": ("Daily limit reached", "This number hit the carrier's daily message cap.", "Try again tomorrow or from another number."),
    "30024": ("Sender not allowed", "The carrier does not accept messages from this kind of number.", "Contact support."),
    "30027": ("T-Mobile daily limit reached", "T-Mobile's daily cap for this number's campaign was reached.", "Try again tomorrow."),
    "30032": ("Toll-free number not verified", "Toll-free numbers must be verified before US carriers deliver their texts.", "Finish toll-free verification (Admin -> Compliance)."),
    "30034": ("Number not registered for business texting", "This number is not on an approved 10DLC campaign, so US carriers block its messages.", "Finish 10DLC registration for this number (Admin -> Compliance)."),
    "30035": ("Attachment too large", "The photo or file exceeded the carrier's size limit.", "Resend with a smaller photo, or as plain text."),
    "30410": ("Carrier timeout", "The carrier did not respond in time.", "Resend."),
    "30001": ("Twilio queue overflow", "Too many messages were queued at once and this one was dropped.", "Resend."),
    "30002": ("Account suspended", "The Twilio account that owns this number is suspended.", "Contact support."),
    "21610": ("Customer opted out", "They replied STOP to this number, so further texts are blocked.", "They need to text START to your number, or call them."),
    "21614": ("Not a mobile number", "This number cannot receive SMS.", "Call instead, or ask for a mobile number."),
    "21211": ("Invalid phone number", "The number is not a valid phone number.", "Fix the number on the contact."),
    "21408": ("Region not enabled", "Texting to this country is not turned on for the account.", "Contact support."),
    "21620": ("Attachment could not be loaded", "Twilio could not fetch the attachment before sending.", "Resend as plain text."),
    "12300": ("Attachment type not accepted", "The carrier does not accept this kind of attachment.", "Resend as plain text."),
    "11200": ("Attachment could not be loaded", "Twilio could not download the attachment.", "Resend as plain text."),
    "21617": ("Message too long", "The text exceeds the carrier's length limit.", "Shorten it and resend."),
}

STALE_AFTER_S = 10 * 60


def _age_s(when: Optional[datetime]) -> Optional[int]:
    if not when:
        return None
    try:
        return int((datetime.utcnow() - when.replace(tzinfo=None)).total_seconds())
    except Exception:
        return None


def explain(msg: dict) -> dict:
    """{title, detail, action, tone, code} for a stored outbound message doc."""
    code = str(msg.get("error_code") or "").strip()
    status = msg.get("status") or ""
    tw = (msg.get("twilio_status") or "").lower()
    had_media = bool(msg.get("has_media") and msg.get("media_urls"))
    age = _age_s(msg.get("status_updated_at") or msg.get("timestamp") or msg.get("created_at"))

    if code in CODES:
        title, detail, action = CODES[code]
        return {"title": title, "detail": detail, "action": action, "tone": "bad", "code": code}
    if status == "failed" or tw in ("failed", "undelivered"):
        raw = msg.get("error_message") or "The carrier rejected it without a reason."
        return {"title": "Not delivered", "detail": raw, "action": "Resend as plain text." if had_media else "Resend, or call them.", "tone": "bad", "code": code or None}
    if status == "delivered" or tw == "delivered":
        return {"title": "Delivered", "detail": "The carrier confirmed it reached the customer's phone.", "action": None, "tone": "good", "code": None}
    if status == "sent_mock" or str(msg.get("twilio_sid") or "").startswith(("MOCK_", "GUARD_")):
        return {"title": "Never sent", "detail": "The server's test-mode send guard held this message, so it never went to the carrier. The customer did not get it.",
                "action": "Resend it.", "tone": "bad", "code": None}
    if status in ("sending", "queued") or tw in ("queued", "accepted", "sending"):
        return {"title": "Queued", "detail": "Twilio has it and is handing it to the carrier.", "action": None, "tone": "muted", "code": None}
    if age is not None and age > STALE_AFTER_S:
        why = "Contact-card and photo attachments are the most common reason." if had_media else "Links and salesy wording are the most common reason."
        return {"title": "Accepted, never confirmed",
                "detail": f"The carrier took the message but never confirmed delivery. After this long that almost always means it was quietly filtered. {why}",
                "action": "Resend as plain text, or call them.", "tone": "warn", "code": None}
    return {"title": "Sent", "detail": "Handed to the carrier. Delivery is usually confirmed within a few minutes.", "action": None, "tone": "muted", "code": None}


def vcard_media_to_link(message: str, media_urls: Optional[list]) -> tuple:
    """Carriers drop .vcf attachments far more often than links: move any contact-card attachment into the text as a link."""
    keep, links = [], []
    for u in media_urls or []:
        low = (u or "").lower()
        (links if (".vcf" in low or "/vcard" in low) else keep).append(u)
    for u in links:
        if u not in (message or ""):
            message = f"{(message or '').rstrip()}\n{u}".strip()
    return message, keep
