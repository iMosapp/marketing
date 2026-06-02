"""
Subscriptions & Quotes Router
Handles I'm On Social subscription plans, quotes, and Stripe billing
"""
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import Response
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional
import logging
import os
import asyncio
import base64
import re as _re

from routers.database import get_db

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])
logger = logging.getLogger(__name__)

# ── Email / PDF config ────────────────────────────────────────────────────────
import resend as _resend

_RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
_APP_URL        = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
_ADMIN_EMAIL    = os.environ.get("ADMIN_EMAIL", "forest@imosapp.com")

if _RESEND_API_KEY:
    _resend.api_key = _RESEND_API_KEY


# ── Quote PDF helpers ─────────────────────────────────────────────────────────

def _qt(text: str) -> str:
    """Strip markdown and encode to latin-1 safely for fpdf."""
    text = _re.sub(r'\*\*(.*?)\*\*', r'\1', str(text))
    text = _re.sub(r'\*(.*?)\*',     r'\1', text)
    for src, dst in [('\u2018',"'"),('\u2019',"'"),('\u201c','"'),('\u201d','"'),('\u2014','--'),('\u2013','-'),('\u00a0',' ')]:
        text = text.replace(src, dst)
    return text.encode('latin-1', errors='replace').decode('latin-1')


def _generate_quote_pdf(quote: dict) -> bytes:
    """Generate a professional signed-quote PDF using fpdf2. Returns PDF bytes."""
    from fpdf import FPDF

    GOLD  = (201, 169, 98)
    BLACK = (10,  10,  10)
    GREY  = (80,  80,  80)
    LGREY = (200, 200, 200)
    WHITE = (255, 255, 255)
    GREEN = (52,  199, 89)
    BLUE  = (0,   122, 255)

    sig       = quote.get("digital_signature") or {}
    customer  = quote.get("customer") or {}
    biz       = quote.get("business_info") or {}
    pricing   = quote.get("pricing") or {}
    plan_type = quote.get("plan_type", "individual")
    accepted_at = quote.get("accepted_at")
    if accepted_at and isinstance(accepted_at, datetime):
        accepted_str = accepted_at.strftime("%B %d, %Y at %I:%M %p UTC")
    else:
        accepted_str = str(accepted_at or "N/A")

    pdf = FPDF()
    pdf.set_margins(left=14, top=10, right=14)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    W = pdf.w - pdf.l_margin - pdf.r_margin
    LBL = 52
    VAL = W - LBL

    # Header
    pdf.set_fill_color(*BLACK)
    pdf.rect(0, 0, 210, 38, 'F')
    pdf.set_xy(0, 8)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*GOLD)
    pdf.cell(210, 10, "I'm On Social", align="C", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*LGREY)
    pdf.cell(210, 6, "Subscription Quote & Service Agreement", align="C", ln=True)
    pdf.set_xy(pdf.l_margin, 44)

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*BLACK)
    pdf.cell(W, 12, _qt(quote.get("quote_number", "")), ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*GREY)
    pdf.cell(W, 7, f"Accepted: {accepted_str}", ln=True, align="C")
    pdf.ln(4)

    badge_w = 44
    pdf.set_x(pdf.l_margin + (W - badge_w) / 2)
    pdf.set_fill_color(*GREEN)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(badge_w, 7, "ACCEPTED", align="C", fill=True, border=0, ln=True)
    pdf.set_x(pdf.l_margin)
    pdf.ln(8)

    # Helpers
    def divider():
        pdf.set_x(pdf.l_margin)
        pdf.set_draw_color(*LGREY)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(4)

    def section_header(title: str, color=None):
        pdf.ln(2)
        pdf.set_x(pdf.l_margin)
        pdf.set_fill_color(*(color or GOLD))
        pdf.set_text_color(*WHITE)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(W, 7, f"  {title.upper()}", fill=True, ln=True)
        pdf.set_x(pdf.l_margin)
        pdf.ln(3)
        pdf.set_text_color(*BLACK)

    def lv(label: str, value: str, mono: bool = False):
        if not value:
            return
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*GREY)
        pdf.cell(LBL, 6, _qt(label) + ":", ln=False)
        pdf.set_font("Courier" if mono else "Helvetica", "", 9)
        pdf.set_text_color(*BLACK)
        pdf.multi_cell(VAL, 6, _qt(str(value)))
        pdf.set_x(pdf.l_margin)

    # Customer / Business
    section_header("Customer")
    if biz.get("company_name"):
        lv("Company",  biz["company_name"])
    lv("Contact",   customer.get("name",""))
    lv("Email",     customer.get("email",""))
    lv("Phone",     customer.get("phone",""))
    addr = biz.get("address", {})
    addr_str = ", ".join(p for p in [addr.get("street",""), addr.get("city",""), addr.get("state",""), addr.get("zip","")] if p)
    if addr_str.strip(", "):
        lv("Address", addr_str)
    if biz.get("ein"):
        lv("EIN / Tax ID", biz["ein"])
    signer = biz.get("authorized_signer", {})
    if signer.get("name"):
        lv("Auth. Signer", f"{signer.get('name','')}  {signer.get('title','')}".strip())
    pdf.ln(2)

    # Plan & Pricing
    section_header("Plan & Pricing", BLUE)
    lv("Plan",       quote.get("plan_name",""))
    lv("Plan Type",  "Account / Team" if plan_type == "store" else "Individual")
    if pricing.get("num_users") and plan_type == "store":
        lv("Users",      str(pricing["num_users"]))
        if pricing.get("price_per_user"):
            lv("Per User",   f"${pricing['price_per_user']:.2f}/mo")
    lv("Base Price", f"${pricing.get('base_price',0):.2f}/{pricing.get('interval','mo')}")
    if pricing.get("discount_percent"):
        lv("Discount",   f"{pricing['discount_percent']}% off"
                         + (f" (code: {pricing.get('discount_code','')})" if pricing.get("discount_code") else ""))
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*GREEN)
    pdf.cell(LBL, 8, "TOTAL:", ln=False)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(VAL, 8, f"${pricing.get('final_price',0):.2f}/{pricing.get('interval','mo')}", ln=True)
    pdf.set_x(pdf.l_margin)
    pdf.set_text_color(*BLACK)
    pdf.ln(2)

    # Terms
    section_header("Service Terms")
    terms = [
        ("Cancellation",  "Either party may cancel with 30 days written notice."),
        ("Billing",       "Billed monthly on the date service begins. Prices subject to change with 30 days notice."),
        ("Trial",         f"{pricing.get('trial_days',7)}-day free trial included. No charge during trial."),
        ("Refunds",       "No refunds for partial billing periods."),
        ("Governing Law", "State of Wyoming."),
    ]
    if quote.get("notes"):
        terms.append(("Special Notes", quote["notes"]))
    for label, val in terms:
        lv(label, val)
    pdf.ln(2)

    # Signature Record
    pdf.add_page()
    section_header("Digital Signature Record", GREEN)
    y_start = pdf.get_y()
    rows = [
        ("Signed By",     sig.get("name",""),           False),
        ("Email",         sig.get("email",""),           False),
        ("Signed At",     accepted_str,                  False),
        ("IP Address",    sig.get("ip_address",""),      True),
        ("Signature",     f'"{sig.get("signature","")}"',False),
        ("User Agent",    sig.get("user_agent",""),      True),
        ("Document Hash", sig.get("document_hash",""),   True),
    ]
    for label, value, mono in rows:
        lv(label, value, mono=mono)
    pdf.ln(4)
    y_end = pdf.get_y()
    pdf.set_draw_color(*GREEN)
    pdf.rect(pdf.l_margin - 2, y_start - 1, W + 4, y_end - y_start + 2)
    pdf.ln(6)

    # Payment TODO notice
    section_header("Payment Status", (255, 149, 0))
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(255, 149, 0)
    pdf.multi_cell(W, 6, "PENDING -- Payment information to be collected separately. "
                         "You will receive a payment setup link by email and/or SMS.")
    pdf.set_text_color(*BLACK)
    pdf.ln(4)

    divider()
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(W, 5,
        "This document confirms acceptance of the above subscription quote. "
        "Service terms, cancellation policy, and pricing are binding upon acceptance. "
        "Governed by the laws of the State of Wyoming. I'm On Social is a product of VI Ventures Group LLC."
    )
    pdf.ln(2)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(W, 5, f"Generated {datetime.utcnow().strftime('%B %d, %Y')} | VI Ventures Group LLC", ln=True)

    return bytes(pdf.output())


async def _send_quote_link_email(quote: dict, quote_id: str) -> None:
    """Email the customer a link to review and sign their quote."""
    if not _RESEND_API_KEY:
        logger.warning("[Quotes] RESEND_API_KEY not set — skipping quote email")
        return

    customer    = quote.get("customer") or {}
    biz         = quote.get("business_info") or {}
    pricing     = quote.get("pricing") or {}
    to_email    = customer.get("email")
    if not to_email:
        return

    name        = customer.get("name") or biz.get("company_name") or "there"
    quote_num   = quote.get("quote_number", "")
    plan_name   = quote.get("plan_name", "")
    final_price = pricing.get("final_price", 0)
    interval    = pricing.get("interval", "month")
    valid_until = quote.get("valid_until")
    valid_str   = valid_until.strftime("%B %d, %Y") if isinstance(valid_until, datetime) else str(valid_until or "")
    sign_link   = f"{_APP_URL}/quote/accept/{quote_id}"

    checklist = [
        "Your full pricing & plan details",
        "30-day cancellation policy",
        "Service terms & agreement",
        "Digital signature — legally binding"
    ]
    checklist_html = "".join(
        f'<div style="display:flex;align-items:center;gap:12px;font-size:14px;color:#CCC;margin-bottom:10px;">'
        f'<span style="color:#34C759;font-size:16px;">&#10003;</span> {item}</div>'
        for item in checklist
    )

    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;background:#000;color:#fff;padding:40px 32px;border-radius:16px;">
      <div style="text-align:center;margin-bottom:40px;">
        <div style="display:inline-block;background:#1C1C1E;border-radius:12px;padding:14px 28px;">
          <span style="font-size:22px;font-weight:800;color:#C9A962;">I'm On Social</span>
        </div>
      </div>
      <h1 style="font-size:26px;font-weight:700;color:#fff;margin:0 0 8px;text-align:center;">Your Quote is Ready</h1>
      <p style="font-size:16px;color:#8E8E93;text-align:center;margin:0 0 36px;">Hi {name} — please review and sign below.</p>

      <div style="background:#1C1C1E;border-radius:12px;padding:24px;margin-bottom:28px;border-left:4px solid #C9A962;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <span style="font-size:13px;color:#8E8E93;text-transform:uppercase;letter-spacing:.5px;">Quote</span>
          <span style="font-size:15px;font-weight:700;color:#C9A962;font-family:monospace;">{quote_num}</span>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <span style="font-size:13px;color:#8E8E93;">Plan</span>
          <span style="font-size:15px;font-weight:600;color:#fff;">{plan_name}</span>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <span style="font-size:13px;color:#8E8E93;">Monthly Total</span>
          <span style="font-size:20px;font-weight:800;color:#34C759;">${final_price:.2f}<span style="font-size:13px;color:#8E8E93;">/{interval}</span></span>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span style="font-size:13px;color:#8E8E93;">Valid Until</span>
          <span style="font-size:14px;color:#FF9500;">{valid_str}</span>
        </div>
      </div>

      <div style="background:#1C1C1E;border-radius:12px;padding:20px;margin-bottom:28px;">
        <p style="font-size:14px;font-weight:600;color:#fff;margin:0 0 14px;">This quote includes:</p>
        {checklist_html}
      </div>

      <div style="text-align:center;margin-bottom:36px;">
        <a href="{sign_link}" target="_blank" style="display:inline-block;background:#C9A962;color:#000000;font-size:18px;font-weight:700;padding:18px 52px;border-radius:12px;text-decoration:none;mso-padding-alt:0;border:2px solid #C9A962;">
          Review &amp; Sign Quote
        </a>
        <p style="font-size:12px;color:#636366;margin-top:14px;">
          Can't tap the button? Copy this link:<br>
          <a href="{sign_link}" target="_blank" style="color:#C9A962;word-break:break-all;font-size:13px;">{sign_link}</a>
        </p>
      </div>

      <div style="border-top:1px solid #2C2C2E;padding-top:20px;text-align:center;">
        <p style="font-size:13px;color:#636366;margin:0 0 6px;">Questions? <a href="mailto:support@imonsocial.com" style="color:#C9A962;">support@imonsocial.com</a></p>
        <p style="font-size:12px;color:#48484A;margin:0;">&copy; 2026 VI Ventures Group LLC &middot; I'm On Social</p>
      </div>
    </div>
    """

    try:
        result = await asyncio.to_thread(_resend.Emails.send, {
            "from": "I'm On Social <billing@imonsocial.com>",
            "to": [to_email],
            "reply_to": "support@imonsocial.com",
            "subject": f"I'm On Social Quote — {quote_num}",
            "html": html,
        })
        logger.info(f"[Quotes] Quote link emailed to {to_email}: {result.get('id')}")
    except Exception as e:
        logger.error(f"[Quotes] Failed to email quote link to {to_email}: {e}")


async def _create_quote_payment_session(quote: dict, quote_id: str) -> str | None:
    """
    Create a Stripe Checkout Session for the quote's monthly amount.
    Returns the checkout URL or None if Stripe is not configured.
    """
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        logger.info("[Quotes] STRIPE_API_KEY not set — skipping Stripe session creation")
        return None

    try:
        from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest

        pricing     = quote.get("pricing") or {}
        final_price = float(pricing.get("final_price", 0))
        if final_price <= 0:
            return None

        customer    = quote.get("customer") or {}
        plan_name   = quote.get("plan_name", "I'm On Social")
        quote_num   = quote.get("quote_number", "")

        success_url = f"{_APP_URL}/quote/accept/{quote_id}?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url  = f"{_APP_URL}/quote/accept/{quote_id}?payment=cancelled"

        stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=f"{_APP_URL}/api/webhook/stripe")

        session = await stripe_checkout.create_checkout_session(
            CheckoutSessionRequest(
                amount=final_price,
                currency="usd",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "type":          "quote_payment",
                    "quote_id":      quote_id,
                    "quote_number":  quote_num,
                    "plan_name":     plan_name,
                    "customer_email": customer.get("email", ""),
                },
            )
        )

        # Record in payment_transactions
        db = get_db()
        await db.payment_transactions.insert_one({
            "session_id":      session.session_id,
            "type":            "quote_payment",
            "quote_id":        quote_id,
            "quote_number":    quote_num,
            "amount":          final_price,
            "currency":        "usd",
            "customer_email":  customer.get("email", ""),
            "plan_name":       plan_name,
            "status":          "initiated",
            "payment_status":  "pending",
            "checkout_url":    session.url,
            "created_at":      datetime.utcnow(),
        })

        # Store URL on the quote itself
        await db.subscription_quotes.update_one(
            {"_id": ObjectId(quote_id)},
            {"$set": {
                "stripe_checkout_url":    session.url,
                "stripe_session_id":      session.session_id,
                "payment_status":         "pending",
            }}
        )

        logger.info(f"[Quotes] Stripe session created for {quote_id}: {session.session_id}")
        return session.url

    except Exception as e:
        logger.error(f"[Quotes] Stripe session creation failed for {quote_id}: {e}")
        return None


async def _email_accepted_quote(quote: dict, quote_id: str, stripe_url: str | None = None) -> None:
    """
    After a customer signs:
    1. Generate signed PDF
    2. Email customer their signed copy + payment setup instructions
    3. Email admin a copy
    4. Send SMS (via Twilio service, which falls back to mock) with payment link

    TODO: Replace payment_link with live Stripe Payment Link or Checkout URL
          once Stripe integration is configured. See /subscriptions/quotes/{id}/create-payment
          (endpoint stub already exists, needs STRIPE_API_KEY in .env)
    """
    if not _RESEND_API_KEY:
        logger.warning("[Quotes] RESEND_API_KEY not set — skipping accepted-quote email")
        return

    customer    = quote.get("customer") or {}
    biz         = quote.get("business_info") or {}
    to_email    = customer.get("email")
    to_phone    = customer.get("phone") or (biz.get("authorized_signer") or {}).get("phone")
    name        = customer.get("name") or biz.get("company_name") or "Customer"
    quote_num   = quote.get("quote_number","")
    plan_name   = quote.get("plan_name","")
    pricing     = quote.get("pricing") or {}
    final_price = pricing.get("final_price", 0)
    interval    = pricing.get("interval","month")
    accepted_at = quote.get("accepted_at")
    accepted_str = accepted_at.strftime("%B %d, %Y") if isinstance(accepted_at, datetime) else str(accepted_at or "")

    # ── Payment + W-9 links ───────────────────────────────────────────────────
    # Use live Stripe checkout URL if available, otherwise fall back to pricing page
    payment_link = stripe_url or quote.get("stripe_checkout_url") or f"{_APP_URL}/subscription/pricing"
    # W-9: unique upload link for this quote
    w9_token  = quote.get("w9_token", "")
    w9_link   = f"{_APP_URL}/w9/submit/{w9_token}" if w9_token else None
    # ─────────────────────────────────────────────────────────────────────────

    try:
        pdf_bytes = await asyncio.to_thread(_generate_quote_pdf, quote)
        pdf_b64   = base64.b64encode(pdf_bytes).decode()
    except Exception as e:
        logger.error(f"[Quotes] PDF generation failed for {quote_id}: {e}")
        pdf_b64 = None

    safe_name = _re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:40]
    attachment = [{"filename": f"signed_quote_{safe_name}.pdf", "content": pdf_b64}] if pdf_b64 else []

    # W-9 block — included only when w9_link is available
    w9_html_block = (
        f'<div style="background:#007AFF15;border-radius:12px;padding:24px;margin-bottom:28px;border:1px solid #007AFF;">'
        f'<p style="font-size:16px;font-weight:700;color:#007AFF;margin:0 0 10px;">Also Required: W-9 Form</p>'
        f'<p style="font-size:14px;color:#CCC;line-height:22px;margin:0 0 18px;">'
        f'Please upload your completed W-9 so we can process your account. You can upload a PDF or a photo of the signed form.</p>'
        f'<a href="{w9_link}" style="display:inline-block;background:#007AFF;color:#fff;font-size:16px;font-weight:700;padding:14px 32px;border-radius:10px;text-decoration:none;">'
        f'Upload W-9 &rarr;</a></div>'
    ) if w9_link else ""

    # ── Customer email ────────────────────────────────────────────────────────
    if to_email:
        customer_html = f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;background:#000;color:#fff;padding:40px 32px;border-radius:16px;">
          <div style="text-align:center;margin-bottom:32px;">
            <span style="font-size:22px;font-weight:800;color:#C9A962;">I'm On Social</span>
          </div>
          <div style="text-align:center;margin-bottom:32px;">
            <div style="font-size:56px;margin-bottom:16px;">&#x2705;</div>
            <h1 style="font-size:26px;font-weight:700;color:#fff;margin:0 0 8px;">Quote Accepted!</h1>
            <p style="font-size:16px;color:#8E8E93;margin:0;">Your signed agreement is attached. One step left.</p>
          </div>
          <div style="background:#1C1C1E;border-radius:12px;padding:24px;margin-bottom:24px;border-left:4px solid #C9A962;">
            <p style="font-size:13px;color:#8E8E93;margin:0 0 4px;text-transform:uppercase;letter-spacing:.5px;">Plan</p>
            <p style="font-size:18px;font-weight:700;color:#fff;margin:0 0 12px;">{plan_name}</p>
            <p style="font-size:13px;color:#8E8E93;margin:0 0 4px;text-transform:uppercase;letter-spacing:.5px;">Monthly Total</p>
            <p style="font-size:22px;font-weight:800;color:#34C759;margin:0 0 12px;">${final_price:.2f}/{interval}</p>
            <p style="font-size:13px;color:#8E8E93;margin:0 0 4px;text-transform:uppercase;letter-spacing:.5px;">Accepted</p>
            <p style="font-size:14px;color:#fff;margin:0;">{accepted_str}</p>
          </div>
          <div style="background:#FF950015;border-radius:12px;padding:24px;margin-bottom:28px;border:1px solid #FF9500;">
            <p style="font-size:16px;font-weight:700;color:#FF9500;margin:0 0 10px;">Next Step: Set Up Payment</p>
            <p style="font-size:14px;color:#CCC;line-height:22px;margin:0 0 18px;">
              To activate your account, please add your payment information. Your billing starts after your free trial ends.
            </p>
            <a href="{payment_link}" style="display:inline-block;background:#FF9500;color:#000;font-size:16px;font-weight:700;padding:14px 32px;border-radius:10px;text-decoration:none;">
              Set Up Payment &rarr;
            </a>
          </div>
          {w9_html_block}
          <p style="font-size:13px;color:#8E8E93;line-height:20px;margin-bottom:24px;">
            Your signed quote PDF is attached to this email. Keep it for your records.<br>
            Cancellation: 30 days written notice. Questions? Reply to this email.
          </p>
          <div style="border-top:1px solid #2C2C2E;padding-top:20px;text-align:center;">
            <p style="font-size:13px;color:#636366;margin:0 0 6px;"><a href="mailto:support@imonsocial.com" style="color:#C9A962;">support@imonsocial.com</a></p>
            <p style="font-size:12px;color:#48484A;margin:0;">&copy; 2026 VI Ventures Group LLC &middot; I'm On Social</p>
          </div>
        </div>
        """
        try:
            r = await asyncio.to_thread(_resend.Emails.send, {
                "from": "I'm On Social <billing@imonsocial.com>",
                "to": [to_email],
                "reply_to": "support@imonsocial.com",
                "subject": f"Signed: {quote_num} — Next Step: Set Up Payment",
                "html": customer_html,
                "attachments": attachment,
            })
            logger.info(f"[Quotes] Accepted-quote email sent to {to_email}: {r.get('id')}")
        except Exception as e:
            logger.error(f"[Quotes] Failed to email customer {to_email}: {e}")

    # ── Admin email ───────────────────────────────────────────────────────────
    admin_html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;background:#000;color:#fff;padding:40px 32px;border-radius:16px;">
      <div style="text-align:center;margin-bottom:28px;"><span style="font-size:22px;font-weight:800;color:#C9A962;">I'm On Social</span></div>
      <h1 style="font-size:20px;font-weight:700;color:#fff;margin:0 0 6px;">Quote Accepted</h1>
      <p style="font-size:14px;color:#8E8E93;margin:0 0 24px;">A customer just signed their quote. Payment setup link was sent.</p>
      <div style="background:#1C1C1E;border-radius:12px;padding:20px;margin-bottom:16px;">
        <p style="font-size:13px;color:#8E8E93;margin:0 0 3px;">Customer</p>
        <p style="font-size:16px;font-weight:700;color:#fff;margin:0 0 12px;">{name}</p>
        <p style="font-size:13px;color:#8E8E93;margin:0 0 3px;">Email</p>
        <p style="font-size:14px;color:#fff;margin:0 0 12px;">{to_email or "N/A"}</p>
        <p style="font-size:13px;color:#8E8E93;margin:0 0 3px;">Quote / Plan</p>
        <p style="font-size:14px;color:#fff;margin:0 0 12px;">{quote_num} &mdash; {plan_name}</p>
        <p style="font-size:13px;color:#8E8E93;margin:0 0 3px;">MRR</p>
        <p style="font-size:18px;font-weight:800;color:#34C759;margin:0;">${final_price:.2f}/{interval}</p>
      </div>
      <p style="font-size:11px;color:#48484A;text-align:center;margin:0;">&copy; 2026 VI Ventures Group LLC</p>
    </div>
    """
    try:
        r = await asyncio.to_thread(_resend.Emails.send, {
            "from": "I'm On Social <billing@imonsocial.com>",
            "to": [_ADMIN_EMAIL],
            "reply_to": "support@imonsocial.com",
            "subject": f"[Quote Signed] {name} — {plan_name} ${final_price:.2f}/{interval}",
            "html": admin_html,
            "attachments": attachment,
        })
        logger.info(f"[Quotes] Admin copy sent to {_ADMIN_EMAIL}: {r.get('id')}")
    except Exception as e:
        logger.error(f"[Quotes] Failed to email admin: {e}")

    # ── SMS (Twilio — falls back to mock if not configured) ───────────────────
    # Send payment link SMS from the rep/admin's Twilio number
    if to_phone:
        try:
            from services.twilio_service import send_sms
            sms_body = (
                f"Hi {name.split()[0]}! Your I'm On Social quote is signed. "
                f"Final step: set up payment to activate your account: {payment_link}"
            )
            # Use the quote owner's Twilio number if available
            rep_twilio_num = None
            try:
                quote_owner_id = quote.get("created_by") or quote.get("user_id")
                if quote_owner_id:
                    owner = await db.users.find_one({"_id": ObjectId(str(quote_owner_id))}, {"twilio_number": 1, "mvpline_number": 1})
                    rep_twilio_num = (owner or {}).get("twilio_number") or (owner or {}).get("mvpline_number")
            except Exception:
                pass
            result = await send_sms(to_phone, sms_body, from_phone=rep_twilio_num)
            logger.info(f"[Quotes] Payment SMS sent to {to_phone}: {result}")
        except Exception as e:
            logger.warning(f"[Quotes] SMS send failed (non-fatal): {e}")



# ============= PRICING PLANS =============
# These are fixed server-side - NEVER accept amounts from frontend

# Individual Plans
INDIVIDUAL_PLANS = {
    "monthly": {
        "id": "monthly",
        "name": "Monthly",
        "type": "individual",
        "price": 100.00,
        "interval": "month",
        "trial_days": 7,
        "description": "Month-to-month flexibility",
        "features": [
            "Full I'm On Social access",
            "Unlimited contacts",
            "AI-powered messaging",
            "Campaign automation",
            "7-day free trial",
            "Cancel with 30 days notice"
        ],
        "badge": None,
    },
    "annual": {
        "id": "annual",
        "name": "Annual",
        "type": "individual",
        "price": 1000.00,
        "interval": "year",
        "trial_days": 7,
        "description": "Best value - Save $200/year",
        "original_price": 1200.00,
        "discount_percent": 17,
        "features": [
            "Everything in Monthly",
            "Save $200 per year",
            "Priority support",
            "7-day free trial",
            "Annual commitment"
        ],
        "badge": "BEST VALUE",
    },
    "intro": {
        "id": "intro",
        "name": "Introductory Offer",
        "type": "individual",
        "price": 50.00,
        "interval": "month",
        "trial_days": 14,
        "intro_months": 3,
        "regular_price": 100.00,
        "description": "Special offer for new customers",
        "features": [
            "Full I'm On Social access",
            "$50/month for first 3 months",
            "Then $100/month",
            "14-day free trial",
            "No commitment"
        ],
        "badge": "LIMITED TIME",
        "terms": "After 3 months, billing continues at $100/month"
    }
}

# Store/Business Plans (per user pricing)
STORE_PLANS = {
    "store_standard": {
        "id": "store_standard",
        "name": "Store Plan",
        "type": "store",
        "price_per_user": 75.00,
        "min_users": 5,
        "interval": "month",
        "trial_days": 7,
        "description": "For dealerships & sales teams",
        "features": [
            "$75/user per month",
            "Minimum 5 users",
            "Team management dashboard",
            "Store-level analytics",
            "Shared contact lists",
            "Campaign templates",
            "7-day free trial",
            "Cancel with 30 days notice"
        ],
        "badge": "TEAMS",
    },
    "store_volume": {
        "id": "store_volume",
        "name": "Store Plan (6+ Users)",
        "type": "store",
        "price_per_user": 65.00,
        "min_users": 6,
        "interval": "month",
        "trial_days": 7,
        "description": "Volume discount for larger teams",
        "original_price_per_user": 75.00,
        "discount_percent": 13,
        "features": [
            "$65/user per month",
            "6+ users",
            "Save $10/user/month",
            "Everything in Store Plan",
            "Priority onboarding",
            "Dedicated support",
            "7-day free trial"
        ],
        "badge": "BEST FOR TEAMS",
    },
}

# Combined pricing
PRICING_PLANS = {**INDIVIDUAL_PLANS, **STORE_PLANS}


def calculate_store_price(num_users: int) -> dict:
    """Calculate store pricing based on number of users"""
    if num_users < 5:
        return {
            "error": True,
            "message": "Minimum 5 users required for store plans",
            "min_users": 5
        }
    
    if num_users >= 6:
        price_per_user = 65.00
        plan_id = "store_volume"
        discount = (75.00 - 65.00) * num_users
    else:
        price_per_user = 75.00
        plan_id = "store_standard"
        discount = 0
    
    total = price_per_user * num_users
    
    return {
        "error": False,
        "plan_id": plan_id,
        "num_users": num_users,
        "price_per_user": price_per_user,
        "total_monthly": total,
        "total_annual": total * 12,
        "discount_monthly": discount,
        "discount_annual": discount * 12,
    }


@router.get("/plans")
async def get_pricing_plans(plan_type: Optional[str] = None):
    """Get all available subscription plans"""
    if plan_type == "individual":
        plans = list(INDIVIDUAL_PLANS.values())
    elif plan_type == "store":
        plans = list(STORE_PLANS.values())
    else:
        plans = list(PRICING_PLANS.values())
    
    return {
        "plans": plans,
        "currency": "usd",
        "terms": {
            "cancellation": "Cancel anytime with 30 days notice",
            "trial": "All plans include a free trial period",
            "refund": "No refunds for partial billing periods"
        }
    }


@router.get("/plans/store/calculate")
async def calculate_store_pricing(num_users: int):
    """Calculate pricing for store plan based on number of users"""
    return calculate_store_price(num_users)


@router.get("/plans/{plan_id}")
async def get_plan_details(plan_id: str):
    """Get details for a specific plan"""
    if plan_id not in PRICING_PLANS:
        raise HTTPException(status_code=404, detail="Plan not found")
    return PRICING_PLANS[plan_id]


# ============= DISCOUNT CODES =============

DISCOUNT_TIERS = [5, 10, 15, 20, 25]  # Available discount percentages

@router.get("/discount-codes")
async def list_discount_codes(active_only: bool = True):
    """List all discount codes"""
    db = get_db()
    
    query = {}
    if active_only:
        query["status"] = "active"
        query["expires_at"] = {"$gt": datetime.utcnow()}
    
    codes = await db.discount_codes.find(query).sort("created_at", -1).to_list(100)
    
    for code in codes:
        code["_id"] = str(code["_id"])
    
    return codes


@router.post("/discount-codes")
async def create_discount_code(data: dict):
    """Create a new discount code"""
    db = get_db()
    
    code = data.get("code", "").upper().strip()
    discount_percent = data.get("discount_percent", 10)
    max_uses = data.get("max_uses")  # None = unlimited
    expires_days = data.get("expires_days", 90)
    description = data.get("description", "")
    plan_types = data.get("plan_types", ["individual", "store"])  # Which plans it applies to
    
    if not code:
        # Generate a random code
        import secrets, string
        alphabet = string.ascii_uppercase + string.digits
        code = "MVP" + ''.join(secrets.choice(alphabet) for _ in range(6))
    
    if discount_percent not in DISCOUNT_TIERS:
        raise HTTPException(status_code=400, detail=f"Discount must be one of: {DISCOUNT_TIERS}")
    
    # Check for duplicate
    existing = await db.discount_codes.find_one({"code": code})
    if existing:
        raise HTTPException(status_code=400, detail="Code already exists")
    
    discount_code = {
        "code": code,
        "discount_percent": discount_percent,
        "max_uses": max_uses,
        "times_used": 0,
        "plan_types": plan_types,
        "description": description,
        "status": "active",
        "expires_at": datetime.utcnow() + timedelta(days=expires_days),
        "created_at": datetime.utcnow(),
    }
    
    result = await db.discount_codes.insert_one(discount_code)
    discount_code["_id"] = str(result.inserted_id)
    
    logger.info(f"Discount code {code} created with {discount_percent}% off")
    return discount_code


@router.get("/discount-codes/validate/{code}")
async def validate_discount_code(code: str, plan_type: str = "individual"):
    """Validate a discount code"""
    db = get_db()
    
    discount = await db.discount_codes.find_one({
        "code": code.upper(),
        "status": "active",
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    if not discount:
        return {"valid": False, "message": "Invalid or expired code"}
    
    if discount.get("max_uses") and discount["times_used"] >= discount["max_uses"]:
        return {"valid": False, "message": "Code has reached maximum uses"}
    
    if plan_type not in discount.get("plan_types", ["individual", "store"]):
        return {"valid": False, "message": f"Code not valid for {plan_type} plans"}
    
    return {
        "valid": True,
        "discount_percent": discount["discount_percent"],
        "description": discount.get("description", ""),
    }


@router.delete("/discount-codes/{code_id}")
async def deactivate_discount_code(code_id: str):
    """Deactivate a discount code"""
    db = get_db()
    
    result = await db.discount_codes.update_one(
        {"_id": ObjectId(code_id)},
        {"$set": {"status": "inactive"}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Code not found")
    
    return {"message": "Code deactivated"}


# ============= QUOTES =============

@router.post("/quotes")
async def create_quote(data: dict):
    """Create a new subscription quote with full business details"""
    db = get_db()
    
    # Plan selection
    plan_type = data.get("plan_type", "individual")  # individual or store
    plan_id = data.get("plan_id")
    num_users = data.get("num_users", 1)
    
    # Customer info
    customer_email = data.get("email")
    customer_name = data.get("name")
    customer_phone = data.get("phone")
    customer_title = data.get("title", "")
    
    # Business info (for store plans / 10DLC compliance)
    business_info = {
        "company_name": data.get("company_name", ""),
        "website": data.get("website", ""),
        "address": {
            "street": data.get("street_address", ""),
            "city": data.get("city", ""),
            "state": data.get("state", ""),
            "zip": data.get("zip_code", ""),
            "country": data.get("country", "USA"),
        },
        "ein": data.get("ein", ""),  # Employer Identification Number
        "business_type": data.get("business_type", ""),  # LLC, Corp, etc.
        "w9_required": data.get("w9_required", False),
        "authorized_signer": {
            "name": data.get("signer_name", ""),
            "title": data.get("signer_title", ""),
            "email": data.get("signer_email", ""),
            "phone": data.get("signer_phone", ""),
        },
        # 10DLC fields for Twilio compliance
        "ten_dlc": {
            "brand_name": data.get("brand_name", ""),
            "vertical": data.get("vertical", ""),  # Industry type
            "use_case": data.get("use_case", "MIXED"),  # SMS use case
            "sample_messages": data.get("sample_messages", []),
        }
    }
    
    # Quote preparer info
    prepared_by = {
        "name": data.get("prepared_by_name", ""),
        "email": data.get("prepared_by_email", ""),
        "company": data.get("our_company_name", "I'm On Social"),
        "address": data.get("our_company_address", ""),
    }
    
    # Discount handling
    discount_percent = data.get("discount_percent", 0)
    discount_code = data.get("discount_code", "")
    
    # Validate discount
    if discount_code:
        code_validation = await validate_discount_code(discount_code, plan_type)
        if code_validation["valid"]:
            discount_percent = code_validation["discount_percent"]
        else:
            raise HTTPException(status_code=400, detail=code_validation["message"])
    
    if discount_percent > 100:
        raise HTTPException(status_code=400, detail="Discount cannot exceed 100%")
    
    notes = data.get("notes", "")
    valid_days = data.get("valid_days", 30)
    
    # Determine plan and pricing
    if plan_type == "store":
        if num_users < 5:
            raise HTTPException(status_code=400, detail="Minimum 5 users for store plans")
        
        store_pricing = calculate_store_price(num_users)
        if store_pricing.get("error"):
            raise HTTPException(status_code=400, detail=store_pricing["message"])
        
        base_price = store_pricing["total_monthly"]
        price_per_user = store_pricing["price_per_user"]
        plan_name = f"Store Plan ({num_users} users)"
        interval = "month"
        trial_days = 7
    else:
        if not plan_id or plan_id not in INDIVIDUAL_PLANS:
            plan_id = "monthly"  # Default to monthly
        
        plan = INDIVIDUAL_PLANS[plan_id]
        base_price = plan["price"]
        price_per_user = None
        plan_name = plan["name"]
        interval = plan["interval"]
        trial_days = plan["trial_days"]
    
    # Apply discount — or use custom price override if provided
    custom_price = data.get("custom_price")
    if custom_price is not None:
        try:
            final_price = float(custom_price)
            discount_amount = base_price - final_price
            discount_percent = round((discount_amount / base_price * 100), 1) if base_price > 0 else 0
        except (ValueError, TypeError):
            custom_price = None
            discount_amount = (base_price * discount_percent / 100) if discount_percent else 0
            final_price = base_price - discount_amount
    else:
        discount_amount = (base_price * discount_percent / 100) if discount_percent else 0
        final_price = base_price - discount_amount
    
    quote = {
        "quote_number": f"Q-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "plan_type": plan_type,
        "plan_id": plan_id if plan_type == "individual" else "store",
        "plan_name": plan_name,
        
        "customer": {
            "email": customer_email,
            "name": customer_name,
            "phone": customer_phone,
            "title": customer_title,
        },
        
        "business_info": business_info,
        "prepared_by": prepared_by,
        
        "pricing": {
            "base_price": base_price,
            "discount_percent": discount_percent,
            "discount_amount": discount_amount,
            "discount_code": discount_code if discount_code else None,
            "final_price": final_price,
            "interval": interval,
            "trial_days": trial_days,
            "currency": "usd",
            "num_users": num_users if plan_type == "store" else 1,
            "price_per_user": price_per_user,
        },
        
        "notes": notes,
        "status": "draft",  # draft, sent, viewed, accepted, expired, cancelled
        "valid_until": datetime.utcnow() + timedelta(days=valid_days),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    
    result = await db.subscription_quotes.insert_one(quote)
    quote["_id"] = str(result.inserted_id)
    
    # Mark discount code as used if applicable
    if discount_code:
        await db.discount_codes.update_one(
            {"code": discount_code.upper()},
            {"$inc": {"times_used": 1}}
        )
    
    logger.info(f"Quote {quote['quote_number']} created for {customer_email or business_info.get('company_name')}")
    return quote


@router.get("/quotes")
async def list_quotes(status: Optional[str] = None):
    """List all quotes (admin only in future)"""
    db = get_db()
    
    query = {}
    if status:
        query["status"] = status
    
    quotes = await db.subscription_quotes.find(query).sort("created_at", -1).to_list(100)
    
    for quote in quotes:
        quote["_id"] = str(quote["_id"])
    
    return quotes


@router.get("/quotes/{quote_id}")
async def get_quote(quote_id: str):
    """Get a specific quote by ID"""
    db = get_db()
    
    quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    quote["_id"] = str(quote["_id"])
    
    # Check if expired
    if quote["status"] == "pending" and quote["valid_until"] < datetime.utcnow():
        quote["status"] = "expired"
        await db.subscription_quotes.update_one(
            {"_id": ObjectId(quote_id)},
            {"$set": {"status": "expired"}}
        )
    
    return quote


@router.patch("/quotes/{quote_id}")
async def update_quote(quote_id: str, data: dict):
    """Update a quote (notes, status, etc.)"""
    db = get_db()
    
    quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    # Only allow updating certain fields
    allowed_fields = ["notes", "status", "valid_until"]
    update_dict = {k: v for k, v in data.items() if k in allowed_fields}
    update_dict["updated_at"] = datetime.utcnow()
    
    await db.subscription_quotes.update_one(
        {"_id": ObjectId(quote_id)},
        {"$set": update_dict}
    )
    
    return {"message": "Quote updated successfully"}


@router.post("/quotes/{quote_id}/send")
async def send_quote(quote_id: str):
    """Send/resend a quote to the customer via email"""
    db = get_db()

    quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    customer_email = quote.get("customer", {}).get("email")
    if not customer_email:
        raise HTTPException(status_code=400, detail="No customer email on this quote")

    await db.subscription_quotes.update_one(
        {"_id": ObjectId(quote_id)},
        {"$set": {"status": "sent", "sent_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
    )
    quote["status"] = "sent"

    await _send_quote_link_email(quote, quote_id)
    logger.info(f"Quote {quote['quote_number']} sent to {customer_email}")

    return {"message": "Quote sent successfully", "sent_to": customer_email}


@router.get("/quotes/{quote_id}/public")
async def get_quote_public(quote_id: str):
    """Public endpoint for the signing page — marks as viewed, never reveals internal fields."""
    db = get_db()
    quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    if quote["status"] == "sent":
        await db.subscription_quotes.update_one(
            {"_id": ObjectId(quote_id)},
            {"$set": {"status": "viewed", "viewed_at": datetime.utcnow()}}
        )
        quote["status"] = "viewed"

    pricing   = quote.get("pricing", {})
    customer  = quote.get("customer", {})
    biz       = quote.get("business_info", {})
    valid_until = quote.get("valid_until")

    return {
        "id": str(quote["_id"]),
        "quote_number": quote.get("quote_number"),
        "status": quote["status"],
        "plan_name": quote.get("plan_name"),
        "plan_type": quote.get("plan_type"),
        "pricing": {
            "base_price":      pricing.get("base_price", 0),
            "discount_percent": pricing.get("discount_percent", 0),
            "final_price":     pricing.get("final_price", 0),
            "interval":        pricing.get("interval", "month"),
            "num_users":       pricing.get("num_users"),
            "price_per_user":  pricing.get("price_per_user"),
            "trial_days":      pricing.get("trial_days", 7),
        },
        "customer": {
            "name":  customer.get("name", ""),
            "email": customer.get("email", ""),
            "phone": customer.get("phone", ""),
        },
        "business_info": {
            "company_name": biz.get("company_name", ""),
        },
        "notes": quote.get("notes", ""),
        "valid_until": valid_until.isoformat() if isinstance(valid_until, datetime) else str(valid_until or ""),
        "digital_signature": quote.get("digital_signature"),
        "accepted_at": quote.get("accepted_at").isoformat() if isinstance(quote.get("accepted_at"), datetime) else None,
        "stripe_checkout_url": quote.get("stripe_checkout_url"),
        "payment_status": quote.get("payment_status", "pending"),
    }


@router.post("/quotes/{quote_id}/accept")
async def accept_quote(quote_id: str, data: dict, request: Request):
    """Customer digitally signs and accepts the quote. Captures IP, timestamp, doc hash."""
    db = get_db()
    quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.get("status") == "accepted":
        raise HTTPException(status_code=400, detail="Quote already accepted")

    # Validate required fields
    name      = (data.get("name") or "").strip()
    email     = (data.get("email") or "").strip()
    signature = (data.get("signature") or "").strip()
    if not name or not email or not signature:
        raise HTTPException(status_code=400, detail="name, email, and signature are required")

    # Legal record
    client_ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.headers.get("X-Real-IP")
        or (request.client.host if request.client else "unknown")
    )
    import hashlib as _hl
    content_str = str(quote.get("quote_number","")) + str(quote.get("pricing",{})) + signature
    doc_hash = _hl.sha256(content_str.encode()).hexdigest()

    now = datetime.utcnow()
    digital_signature = {
        "name":          name,
        "email":         email,
        "signature":     signature,
        "signature_type": "typed",
        "signed_at":     now,
        "ip_address":    client_ip,
        "user_agent":    request.headers.get("User-Agent", ""),
        "document_hash": doc_hash,
        "agreed_to_terms": True,
    }

    import secrets as _secrets
    w9_token = _secrets.token_urlsafe(24)

    await db.subscription_quotes.update_one(
        {"_id": ObjectId(quote_id)},
        {"$set": {
            "status":            "accepted",
            "accepted_at":       now,
            "updated_at":        now,
            "digital_signature": digital_signature,
            "customer.name":     name,
            "customer.email":    email,
            "w9_token":          w9_token,
            "w9_status":         "pending",
        }}
    )

    # Reload with updated data for email/PDF
    stripe_url = None
    updated = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
    if updated:
        # Generate Stripe checkout session for the quote amount (monthly recurring)
        stripe_url = await _create_quote_payment_session(updated, quote_id)
        asyncio.create_task(_email_accepted_quote(updated, quote_id, stripe_url))

    return {
        "success":             True,
        "status":              "accepted",
        "stripe_checkout_url": stripe_url,
        "message": "Quote accepted. Check your email for your signed copy and payment setup link.",
    }


@router.post("/quotes/{quote_id}/create-payment")
async def create_quote_payment(quote_id: str):
    """
    Generate (or regenerate) a Stripe checkout session for an accepted quote.
    Called when customer clicks 'Set Up Monthly Payment' after signing.
    """
    db = get_db()
    quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.get("status") != "accepted":
        raise HTTPException(status_code=400, detail="Quote must be accepted before payment can be set up")
    if quote.get("payment_status") == "paid":
        return {"success": True, "already_paid": True, "message": "Payment already completed"}

    stripe_url = await _create_quote_payment_session(quote, quote_id)
    if not stripe_url:
        raise HTTPException(status_code=503, detail="Payment system not configured. Contact support@imonsocial.com")

    return {"success": True, "checkout_url": stripe_url}


@router.get("/quotes/{quote_id}/payment-status")
async def get_quote_payment_status(quote_id: str, session_id: str | None = None):
    """Poll payment status after returning from Stripe."""
    db = get_db()
    quote = await db.subscription_quotes.find_one(
        {"_id": ObjectId(quote_id)},
        {"payment_status": 1, "stripe_checkout_url": 1, "stripe_session_id": 1, "status": 1}
    )
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    # If session_id provided, check with Stripe directly
    if session_id:
        api_key = os.environ.get("STRIPE_API_KEY")
        if api_key:
            try:
                from emergentintegrations.payments.stripe.checkout import StripeCheckout
                sc = StripeCheckout(api_key=api_key, webhook_url="")
                result = await sc.get_checkout_status(session_id)
                if result.payment_status == "paid":
                    await db.subscription_quotes.update_one(
                        {"_id": ObjectId(quote_id)},
                        {"$set": {"payment_status": "paid", "paid_at": datetime.utcnow()}}
                    )
                    await db.payment_transactions.update_one(
                        {"session_id": session_id},
                        {"$set": {"status": "paid", "payment_status": "paid", "updated_at": datetime.utcnow()}}
                    )
                    return {"payment_status": "paid", "status": quote.get("status")}
            except Exception as e:
                logger.warning(f"[Quotes] Payment status check failed: {e}")

    return {
        "payment_status":      quote.get("payment_status", "pending"),
        "status":              quote.get("status"),
        "stripe_checkout_url": quote.get("stripe_checkout_url"),
    }


async def download_quote_pdf(quote_id: str):
    """Generate and stream the accepted quote as a signed PDF."""
    db = get_db()
    quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.get("status") != "accepted":
        raise HTTPException(status_code=400, detail="Quote has not been accepted yet")

    customer  = quote.get("customer") or {}
    biz       = quote.get("business_info") or {}
    raw_name  = customer.get("name") or biz.get("company_name") or "quote"
    safe_name = _re.sub(r"[^a-zA-Z0-9_-]", "_", raw_name)[:40]
    filename  = f"signed_quote_{safe_name}.pdf"

    pdf_bytes = await asyncio.to_thread(_generate_quote_pdf, quote)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



@router.post("/quotes/{quote_id}/add-contact")
async def add_quote_contact(quote_id: str, request: Request):
    """
    Creates the customer from this quote as a contact in the requesting user's account.
    Returns the contact_id + a pre-filled SMS message with the signing link.
    Idempotent — if a contact with matching phone/email already exists, returns that one.
    """
    db = get_db()
    data = await request.json()
    user_id = data.get("user_id") or request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")

    quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    customer = quote.get("customer") or {}
    biz      = quote.get("business_info") or {}
    pricing  = quote.get("pricing") or {}

    name     = customer.get("name") or biz.get("company_name") or ""
    email    = customer.get("email") or ""
    phone    = customer.get("phone") or ""

    if not phone and not email:
        raise HTTPException(status_code=400, detail="Quote has no phone or email to create contact from")

    # Normalise phone for lookup
    digits = ''.join(c for c in (phone or "") if c.isdigit())

    # Check if contact already exists (same user, matching phone or email)
    existing = None
    if digits:
        existing = await db.contacts.find_one({
            "user_id": user_id,
            "$or": [
                {"phone": {"$regex": digits[-10:]}},
                {"phone_digits": digits[-10:]},
            ]
        })
    if not existing and email:
        existing = await db.contacts.find_one({"user_id": user_id, "email": email.lower().strip()})

    if existing:
        contact_id = str(existing["_id"])
        created = False
    else:
        # Build contact document
        parts      = name.strip().split(" ", 1)
        first_name = parts[0] if parts else name
        last_name  = parts[1] if len(parts) > 1 else ""
        addr       = biz.get("address") or {}

        contact_doc = {
            "user_id":          user_id,
            "original_user_id": user_id,
            "first_name":       first_name,
            "last_name":        last_name,
            "email":            email.lower().strip() if email else "",
            "phone":            phone,
            "company":          biz.get("company_name", ""),
            "address":          addr.get("street", "") if isinstance(addr, dict) else "",
            "city":             addr.get("city", "")   if isinstance(addr, dict) else "",
            "state":            addr.get("state", "")  if isinstance(addr, dict) else "",
            "zip":              addr.get("zip", "")    if isinstance(addr, dict) else "",
            "source":           "quote",
            "ownership_type":   "org",
            "status":           "active",
            "tags":             ["Quote Sent"],
            "notes":            f"Added from quote {quote.get('quote_number','')} — {quote.get('plan_name','')} ${pricing.get('final_price',0):.0f}/mo",
            "created_at":       datetime.utcnow(),
            "updated_at":       datetime.utcnow(),
        }
        result    = await db.contacts.insert_one(contact_doc)
        contact_id = str(result.inserted_id)
        created   = True

    # Build the SMS message
    sign_link  = f"{_APP_URL}/quote/accept/{quote_id}"
    first      = (name.split()[0] if name else "there")
    plan_name  = quote.get("plan_name", "your plan")
    price      = pricing.get("final_price", 0)
    sms_body   = (
        f"Hi {first}! Here's your I'm On Social quote for {plan_name} at ${price:.0f}/mo. "
        f"Review and sign here: {sign_link}"
    )

    return {
        "contact_id": contact_id,
        "created":    created,
        "name":       name,
        "phone":      phone,
        "email":      email,
        "sms_body":   sms_body,
        "sign_link":  sign_link,
    }



@router.delete("/quotes/{quote_id}")
async def delete_quote(quote_id: str):
    """Delete a quote (only drafts can be deleted)"""
    db = get_db()
    
    quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    # Only allow deleting drafts
    if quote["status"] != "draft":
        raise HTTPException(status_code=400, detail="Only draft quotes can be deleted")
    
    await db.subscription_quotes.delete_one({"_id": ObjectId(quote_id)})
    return {"message": "Quote deleted successfully"}


@router.put("/quotes/{quote_id}/archive")
async def archive_quote(quote_id: str):
    """Archive a quote"""
    db = get_db()
    
    quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    await db.subscription_quotes.update_one(
        {"_id": ObjectId(quote_id)},
        {"$set": {"status": "archived", "archived_at": datetime.utcnow()}}
    )
    return {"message": "Quote archived successfully"}



# ============= CHECKOUT & PAYMENT =============

@router.post("/checkout")
async def create_checkout_session(request: Request, data: dict):
    """Create a Stripe checkout session for subscription"""
    from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
    
    db = get_db()
    
    plan_id = data.get("plan_id")
    quote_id = data.get("quote_id")
    origin_url = data.get("origin_url")
    customer_email = data.get("email")
    
    if not origin_url:
        raise HTTPException(status_code=400, detail="Origin URL is required")
    
    # Get plan - amount comes from server only
    if plan_id not in PRICING_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    plan = PRICING_PLANS[plan_id]
    
    # If quote_id provided, verify and use quote data
    quote = None
    if quote_id:
        quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
        if quote:
            customer_email = quote["customer"]["email"]
    
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Payment system not configured")
    
    host_url = str(request.base_url).rstrip('/')
    webhook_url = f"{host_url}/api/webhook/stripe"
    
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
    
    # Build dynamic URLs
    success_url = f"{origin_url}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/subscription/cancel"
    
    # Determine amount - for trial, charge $0 initially (Stripe handles trial)
    # For simplicity, we charge the first payment after trial
    amount = plan["price"]
    
    metadata = {
        "type": "subscription",
        "plan_id": plan_id,
        "plan_name": plan["name"],
        "interval": plan["interval"],
        "trial_days": str(plan["trial_days"]),
        "customer_email": customer_email or "",
    }
    
    if quote_id:
        metadata["quote_id"] = quote_id
    
    try:
        checkout_request = CheckoutSessionRequest(
            amount=amount,
            currency="usd",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata
        )
        
        session = await stripe_checkout.create_checkout_session(checkout_request)
        
        # Create payment transaction record
        transaction = {
            "session_id": session.session_id,
            "type": "subscription",
            "plan_id": plan_id,
            "plan_name": plan["name"],
            "amount": amount,
            "currency": "usd",
            "customer_email": customer_email,
            "quote_id": quote_id,
            "status": "initiated",
            "payment_status": "pending",
            "metadata": metadata,
            "created_at": datetime.utcnow(),
        }
        
        await db.payment_transactions.insert_one(transaction)
        
        # Update quote status if applicable
        if quote_id:
            await db.subscription_quotes.update_one(
                {"_id": ObjectId(quote_id)},
                {"$set": {"status": "checkout_started", "updated_at": datetime.utcnow()}}
            )
        
        logger.info(f"Checkout session created for plan {plan_id}")
        
        return {
            "url": session.url,
            "session_id": session.session_id
        }
        
    except Exception as e:
        logger.error(f"Checkout creation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create checkout: {str(e)}")


@router.get("/checkout/status/{session_id}")
async def get_checkout_status(session_id: str):
    """Get the status of a checkout session"""
    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    
    db = get_db()
    
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Payment system not configured")
    
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url="")
    
    try:
        status = await stripe_checkout.get_checkout_status(session_id)
        
        # Update transaction in database
        update_data = {
            "status": status.status,
            "payment_status": status.payment_status,
            "updated_at": datetime.utcnow(),
        }
        
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": update_data}
        )
        
        # If paid, create subscription record
        if status.payment_status == "paid":
            transaction = await db.payment_transactions.find_one({"session_id": session_id})
            if transaction and not await db.subscriptions.find_one({"session_id": session_id}):
                plan_id = transaction.get("plan_id") or status.metadata.get("plan_id")
                plan = PRICING_PLANS.get(plan_id, {})
                
                # Calculate trial end and billing dates
                trial_days = plan.get("trial_days", 7)
                trial_end = datetime.utcnow() + timedelta(days=trial_days)
                
                subscription = {
                    "session_id": session_id,
                    "customer_email": transaction.get("customer_email"),
                    "plan_id": plan_id,
                    "plan_name": plan.get("name", "Unknown"),
                    "amount": transaction.get("amount"),
                    "interval": plan.get("interval", "month"),
                    "status": "trialing",
                    "trial_end": trial_end,
                    "current_period_start": datetime.utcnow(),
                    "current_period_end": trial_end,
                    "cancel_at_period_end": False,
                    "created_at": datetime.utcnow(),
                }
                
                await db.subscriptions.insert_one(subscription)
                
                # Update quote if applicable
                quote_id = transaction.get("quote_id")
                if quote_id:
                    await db.subscription_quotes.update_one(
                        {"_id": ObjectId(quote_id)},
                        {"$set": {"status": "accepted", "updated_at": datetime.utcnow()}}
                    )
                
                logger.info(f"Subscription created for session {session_id}")
        
        return {
            "status": status.status,
            "payment_status": status.payment_status,
            "amount_total": status.amount_total,
            "currency": status.currency,
        }
        
    except Exception as e:
        logger.error(f"Status check error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to check status: {str(e)}")


# ============= SUBSCRIPTION MANAGEMENT =============

@router.get("/my-subscription")
async def get_my_subscription(email: str):
    """Get subscription for a customer by email"""
    db = get_db()
    
    subscription = await db.subscriptions.find_one(
        {"customer_email": email, "status": {"$ne": "cancelled"}},
        sort=[("created_at", -1)]
    )
    
    if not subscription:
        return {"has_subscription": False}
    
    subscription["_id"] = str(subscription["_id"])
    subscription["has_subscription"] = True
    
    # Calculate days remaining in trial
    if subscription["status"] == "trialing":
        trial_end = subscription.get("trial_end")
        if trial_end:
            days_remaining = (trial_end - datetime.utcnow()).days
            subscription["trial_days_remaining"] = max(0, days_remaining)
    
    return subscription


@router.post("/cancel")
async def request_cancellation(data: dict):
    """Request subscription cancellation (30 days notice)"""
    db = get_db()
    
    email = data.get("email")
    reason = data.get("reason", "")
    
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    subscription = await db.subscriptions.find_one(
        {"customer_email": email, "status": {"$in": ["trialing", "active"]}}
    )
    
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")
    
    # Calculate cancellation date (30 days from now)
    cancel_date = datetime.utcnow() + timedelta(days=30)
    
    await db.subscriptions.update_one(
        {"_id": subscription["_id"]},
        {"$set": {
            "cancel_at_period_end": True,
            "cancellation_requested_at": datetime.utcnow(),
            "cancellation_effective_date": cancel_date,
            "cancellation_reason": reason,
            "updated_at": datetime.utcnow(),
        }}
    )
    
    # Create cancellation record
    cancellation = {
        "subscription_id": str(subscription["_id"]),
        "customer_email": email,
        "reason": reason,
        "requested_at": datetime.utcnow(),
        "effective_date": cancel_date,
        "status": "pending",
    }
    await db.subscription_cancellations.insert_one(cancellation)
    
    logger.info(f"Cancellation requested for {email}, effective {cancel_date}")
    
    return {
        "message": "Cancellation request received",
        "effective_date": cancel_date.isoformat(),
        "notice_days": 30,
    }


@router.get("/cancellation-status")
async def get_cancellation_status(email: str):
    """Check if there's a pending cancellation"""
    db = get_db()
    
    cancellation = await db.subscription_cancellations.find_one(
        {"customer_email": email, "status": "pending"},
        sort=[("requested_at", -1)]
    )
    
    if not cancellation:
        return {"has_pending_cancellation": False}
    
    cancellation["_id"] = str(cancellation["_id"])
    cancellation["has_pending_cancellation"] = True
    
    return cancellation



# ── W-9 Upload ────────────────────────────────────────────────────────────────

@router.get("/w9/{token}")
async def get_w9_quote_info(token: str):
    """Return basic quote info for the W-9 upload page (public — no auth)."""
    db = get_db()
    quote = await db.subscription_quotes.find_one({"w9_token": token}, {"_id": 0, "w9_token": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Invalid or expired W-9 link")
    customer = quote.get("customer") or {}
    biz = quote.get("business_info") or {}
    return {
        "company_name":  biz.get("company_name") or customer.get("name") or "Your Company",
        "plan_name":     quote.get("plan_name", ""),
        "quote_number":  quote.get("quote_number", ""),
        "w9_status":     quote.get("w9_status", "pending"),
    }


@router.post("/w9/{token}/upload")
async def upload_w9(
    token: str,
    file: UploadFile = File(...),
    name: str = Form(default=""),
    email: str = Form(default=""),
):
    """Customer uploads their W-9 document. Public endpoint — no auth needed."""
    from utils.image_storage import put_object, upload_image
    import uuid as _uuid

    db = get_db()
    quote = await db.subscription_quotes.find_one({"w9_token": token})
    if not quote:
        raise HTTPException(status_code=404, detail="Invalid or expired W-9 link")

    if quote.get("w9_status") == "submitted":
        return {"success": True, "message": "W-9 already submitted. We'll review it shortly."}

    content = await file.read()
    content_type = file.content_type or "application/pdf"
    quote_id = str(quote["_id"])
    file_id  = _uuid.uuid4().hex

    # Store in object storage
    is_image = content_type.startswith("image/")
    if is_image:
        result = await upload_image(content, prefix="w9", entity_id=file_id)
        w9_url = f"/api/images/{result['original_path']}" if result else None
    else:
        path = f"imos/w9/{quote_id}/{file_id}.pdf"
        await asyncio.to_thread(put_object, path, content, content_type)
        w9_url = f"/api/images/{path}"

    if not w9_url:
        raise HTTPException(status_code=500, detail="Upload failed — please try again")

    now = datetime.utcnow()
    await db.subscription_quotes.update_one(
        {"_id": quote["_id"]},
        {"$set": {
            "w9_status":       "submitted",
            "w9_file_url":     w9_url,
            "w9_submitted_at": now,
            "w9_submitter_name":  name or quote.get("customer", {}).get("name", ""),
            "w9_submitter_email": email or quote.get("customer", {}).get("email", ""),
        }}
    )
    logger.info(f"[W-9] Submitted for quote {quote_id}")

    # Notify admin
    try:
        company = (quote.get("business_info") or {}).get("company_name") or name or "Customer"
        await db.notifications.insert_one({
            "user_id":    None,  # Super admin — picked up globally
            "type":       "w9_submitted",
            "title":      f"W-9 Received — {company}",
            "message":    f"{company} submitted their W-9. Ready for review.",
            "quote_id":   quote_id,
            "read":       False,
            "dismissed":  False,
            "created_at": now,
        })
    except Exception:
        pass

    return {"success": True, "message": "W-9 submitted successfully. We'll review it shortly."}


# ── Reseller / Partner Portal ─────────────────────────────────────────────────

@router.get("/partner/accounts")
async def get_partner_accounts(partner_id: str, include_deactivated: bool = True):
    """
    List all accounts (quotes) for a reseller/partner.
    Returns both active and deactivated so partners have full visibility.
    """
    db = get_db()
    query: dict = {"partner_id": partner_id}
    if not include_deactivated:
        query["status"] = {"$in": ["active", "accepted", "pending"]}

    quotes = await db.subscription_quotes.find(
        query,
        {"w9_token": 0}  # Never expose w9 tokens in list views
    ).sort("created_at", -1).limit(200).to_list(200)

    result = []
    for q in quotes:
        q["_id"] = str(q["_id"])
        # Serialize dates
        for field in ["created_at", "accepted_at", "updated_at", "w9_submitted_at"]:
            if isinstance(q.get(field), datetime):
                q[field] = q[field].isoformat()
        result.append(q)

    # Summary counts
    statuses = [q.get("status", "pending") for q in result]
    return {
        "accounts":    result,
        "total":       len(result),
        "active":      statuses.count("active"),
        "accepted":    statuses.count("accepted"),
        "pending":     statuses.count("pending"),
        "deactivated": statuses.count("deactivated"),
        "w9_pending":  sum(1 for q in result if q.get("w9_status") == "pending"),
        "w9_submitted":sum(1 for q in result if q.get("w9_status") == "submitted"),
    }
