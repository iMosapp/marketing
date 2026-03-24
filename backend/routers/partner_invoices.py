"""
Partner Invoices Router
Handles monthly invoice generation, waivers, per-store rates, and PDF generation
for white-label partner billing.
"""
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from typing import Optional
from pydantic import BaseModel
import logging
import os
import calendar

from routers.database import get_db, get_user_by_id

router = APIRouter(prefix="/admin/partner-invoices", tags=["Partner Invoices"])
logger = logging.getLogger(__name__)

PDF_DIR = "/app/backend/invoice_pdfs"
os.makedirs(PDF_DIR, exist_ok=True)


async def _require_super_admin(x_user_id: str):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = await get_user_by_id(x_user_id)
    if not user or user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


# ==================== WAIVERS ====================

class WaiverCreate(BaseModel):
    partner_id: str
    store_id: str
    store_name: str = ""
    waived_until: Optional[str] = None
    reason: str = ""


@router.get("/waivers/{partner_id}")
async def list_waivers(partner_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """List all active waivers for a partner."""
    await _require_super_admin(x_user_id)
    db = get_db()
    waivers = await db.billing_waivers.find({"partner_id": partner_id}).to_list(500)
    result = []
    for w in waivers:
        waived_until = w.get("waived_until")
        expired = False
        if waived_until and isinstance(waived_until, datetime):
            expired = datetime.now(timezone.utc) > waived_until.replace(tzinfo=timezone.utc) if waived_until.tzinfo is None else datetime.now(timezone.utc) > waived_until
        result.append({
            "_id": str(w["_id"]),
            "partner_id": w.get("partner_id"),
            "store_id": w.get("store_id"),
            "store_name": w.get("store_name", ""),
            "waived_until": w.get("waived_until").isoformat() if w.get("waived_until") else None,
            "reason": w.get("reason", ""),
            "expired": expired,
            "created_at": w.get("created_at").isoformat() if w.get("created_at") else None,
        })
    return result


@router.post("/waivers")
async def create_waiver(body: WaiverCreate, x_user_id: str = Header(None, alias="X-User-ID")):
    """Create a billing waiver for a store."""
    await _require_super_admin(x_user_id)
    db = get_db()

    # Resolve store name if not provided
    store_name = body.store_name
    if not store_name and body.store_id:
        store = await db.stores.find_one({"_id": ObjectId(body.store_id)}, {"name": 1})
        if store:
            store_name = store.get("name", "")

    waiver = {
        "partner_id": body.partner_id,
        "store_id": body.store_id,
        "store_name": store_name,
        "waived_until": datetime.fromisoformat(body.waived_until) if body.waived_until else None,
        "reason": body.reason,
        "created_by": x_user_id,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.billing_waivers.insert_one(waiver)
    waiver["_id"] = str(result.inserted_id)
    waiver["created_at"] = waiver["created_at"].isoformat()
    if waiver["waived_until"]:
        waiver["waived_until"] = waiver["waived_until"].isoformat()
    return waiver


@router.delete("/waivers/{waiver_id}")
async def delete_waiver(waiver_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Remove a billing waiver."""
    await _require_super_admin(x_user_id)
    db = get_db()
    result = await db.billing_waivers.delete_one({"_id": ObjectId(waiver_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Waiver not found")
    return {"success": True}


# ==================== STORE RATES ====================

@router.get("/store-rates/{partner_id}")
async def get_store_rates(partner_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Get per-store billing rates for a partner's stores."""
    await _require_super_admin(x_user_id)
    db = get_db()
    stores = await db.stores.find(
        {"partner_id": partner_id, "active": {"$ne": False}},
        {"_id": 1, "name": 1, "billing_rate": 1, "billing_package": 1}
    ).to_list(500)
    return [
        {
            "_id": str(s["_id"]),
            "name": s.get("name", ""),
            "billing_rate": s.get("billing_rate"),
            "billing_package": s.get("billing_package", ""),
        }
        for s in stores
    ]


@router.put("/store-rate/{store_id}")
async def set_store_rate(store_id: str, body: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Set a per-store billing rate override."""
    await _require_super_admin(x_user_id)
    db = get_db()
    update = {}
    if "billing_rate" in body:
        update["billing_rate"] = float(body["billing_rate"]) if body["billing_rate"] is not None else None
    if "billing_package" in body:
        update["billing_package"] = body["billing_package"]
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    update["updated_at"] = datetime.now(timezone.utc)
    result = await db.stores.update_one({"_id": ObjectId(store_id)}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Store not found")
    return {"success": True}


# ==================== INVOICE GENERATION ====================

async def _generate_invoice_for_partner(partner_id: str, period: str, created_by: str = None) -> dict:
    """
    Generate an invoice for a partner for a given period (YYYY-MM).
    Returns the created invoice dict.
    """
    db = get_db()

    partner = await db.white_label_partners.find_one({"_id": ObjectId(partner_id)})
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    billing_config = partner.get("billing_config", {})
    default_rate = billing_config.get("rate")

    # Parse period
    year, month = int(period[:4]), int(period[5:7])
    period_start = datetime(year, month, 1, tzinfo=timezone.utc)
    last_day = calendar.monthrange(year, month)[1]
    period_end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

    # Check for existing invoice for this period
    existing = await db.partner_invoices.find_one({
        "partner_id": partner_id,
        "period": period,
    })
    if existing:
        raise HTTPException(status_code=409, detail=f"Invoice already exists for {period}")

    # Get all active stores for this partner
    stores = await db.stores.find(
        {"partner_id": partner_id, "active": {"$ne": False}},
        {"_id": 1, "name": 1, "billing_rate": 1, "billing_package": 1, "created_at": 1}
    ).to_list(500)

    # Get active waivers
    waivers = await db.billing_waivers.find({"partner_id": partner_id}).to_list(500)
    waiver_map = {}
    for w in waivers:
        waived_until = w.get("waived_until")
        # Check if waiver is still active for this period
        if waived_until:
            if isinstance(waived_until, datetime):
                wu = waived_until.replace(tzinfo=timezone.utc) if waived_until.tzinfo is None else waived_until
                if wu < period_start:
                    continue  # Waiver expired before this period
        waiver_map[w.get("store_id")] = w

    # Build line items
    line_items = []
    subtotal = 0.0
    for store in stores:
        sid = str(store["_id"])
        store_rate = store.get("billing_rate") if store.get("billing_rate") is not None else default_rate
        waiver = waiver_map.get(sid)
        is_waived = waiver is not None

        amount = 0.0 if is_waived else (store_rate or 0.0)
        subtotal += amount

        item = {
            "store_id": sid,
            "store_name": store.get("name", "Unknown"),
            "billing_package": store.get("billing_package", ""),
            "rate": store_rate or 0.0,
            "waived": is_waived,
            "waiver_reason": waiver.get("reason", "") if waiver else None,
            "waiver_until": waiver.get("waived_until").isoformat() if waiver and waiver.get("waived_until") else ("Indefinite" if waiver else None),
            "amount": amount,
        }
        line_items.append(item)

    # Generate invoice number
    count = await db.partner_invoices.count_documents({})
    invoice_number = f"WL-{period.replace('-', '')}-{str(count + 1).zfill(4)}"

    # Get partner contact info
    partner_user_id = partner.get("user_id")
    partner_email = partner.get("email", "")
    partner_name = partner.get("name", "")
    if partner_user_id and not partner_email:
        pu = await db.users.find_one({"_id": ObjectId(partner_user_id)}, {"email": 1})
        if pu:
            partner_email = pu.get("email", "")

    due_date = datetime(year, month, last_day, tzinfo=timezone.utc) + timedelta(days=15)

    invoice = {
        "partner_id": partner_id,
        "partner_name": partner_name,
        "partner_email": partner_email,
        "invoice_number": invoice_number,
        "period": period,
        "period_start": period_start,
        "period_end": period_end,
        "line_items": line_items,
        "subtotal": round(subtotal, 2),
        "tax": 0.0,
        "total": round(subtotal, 2),
        "status": "draft",
        "pdf_path": None,
        "sent_at": None,
        "paid_at": None,
        "due_date": due_date,
        "notes": "",
        "created_at": datetime.now(timezone.utc),
        "created_by": created_by,
    }

    result = await db.partner_invoices.insert_one(invoice)
    invoice_id = str(result.inserted_id)

    # Generate PDF
    pdf_path = _generate_invoice_pdf(invoice_id, invoice)
    await db.partner_invoices.update_one(
        {"_id": result.inserted_id},
        {"$set": {"pdf_path": pdf_path}}
    )

    invoice["_id"] = invoice_id
    invoice["pdf_path"] = pdf_path
    # Serialize datetimes
    for key in ["period_start", "period_end", "due_date", "created_at"]:
        if isinstance(invoice.get(key), datetime):
            invoice[key] = invoice[key].isoformat()
    return invoice


def _generate_invoice_pdf(invoice_id: str, invoice: dict) -> str:
    """Generate a PDF invoice and return the file path."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Header
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 12, "INVOICE", ln=True, align="R")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, "i'M On Social", ln=True, align="R")
    pdf.cell(0, 6, "support@imonsocial.com", ln=True, align="R")
    pdf.ln(6)

    # Invoice meta
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(95, 7, f"Bill To: {invoice.get('partner_name', '')}", ln=False)
    pdf.cell(95, 7, f"Invoice #: {invoice.get('invoice_number', '')}", ln=True, align="R")
    pdf.set_font("Helvetica", "", 10)
    if invoice.get("partner_email"):
        pdf.cell(95, 6, f"{invoice['partner_email']}", ln=False)
    else:
        pdf.cell(95, 6, "", ln=False)
    period = invoice.get("period", "")
    pdf.cell(95, 6, f"Period: {period}", ln=True, align="R")

    due = invoice.get("due_date")
    if isinstance(due, datetime):
        due_str = due.strftime("%B %d, %Y")
    elif isinstance(due, str):
        due_str = due[:10]
    else:
        due_str = ""
    pdf.cell(95, 6, "", ln=False)
    pdf.cell(95, 6, f"Due Date: {due_str}", ln=True, align="R")

    created = invoice.get("created_at")
    if isinstance(created, datetime):
        created_str = created.strftime("%B %d, %Y")
    elif isinstance(created, str):
        created_str = created[:10]
    else:
        created_str = ""
    pdf.cell(95, 6, "", ln=False)
    pdf.cell(95, 6, f"Date: {created_str}", ln=True, align="R")
    pdf.ln(10)

    # Table header
    pdf.set_fill_color(30, 30, 30)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(80, 9, "  Store / Account", fill=True)
    pdf.cell(40, 9, "Package", fill=True, align="C")
    pdf.cell(30, 9, "Rate", fill=True, align="R")
    pdf.cell(40, 9, "Amount  ", fill=True, align="R")
    pdf.ln()

    # Table rows
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    line_items = invoice.get("line_items", [])
    for i, item in enumerate(line_items):
        bg = (245, 245, 245) if i % 2 == 0 else (255, 255, 255)
        pdf.set_fill_color(*bg)
        name = item.get("store_name", "")[:35]
        package = item.get("billing_package", "")[:20]
        rate_str = f"${item.get('rate', 0):,.2f}"
        if item.get("waived"):
            amount_str = "$0.00"
            waiver_note = item.get("waiver_reason") or "Waived"
            if item.get("waiver_until") and item["waiver_until"] != "Indefinite":
                waiver_note += f" (until {item['waiver_until'][:10]})"
            elif item.get("waiver_until") == "Indefinite":
                waiver_note += " (indefinite)"
        else:
            amount_str = f"${item.get('amount', 0):,.2f}"
            waiver_note = None

        pdf.cell(80, 8, f"  {name}", fill=True)
        pdf.cell(40, 8, package, fill=True, align="C")
        pdf.cell(30, 8, rate_str, fill=True, align="R")
        pdf.cell(40, 8, f"{amount_str}  ", fill=True, align="R")
        pdf.ln()

        if waiver_note:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(80, 6, f"    {waiver_note}", ln=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(0, 0, 0)

    # Totals
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(150, 8, "Subtotal:", align="R")
    pdf.cell(40, 8, f"${invoice.get('subtotal', 0):,.2f}  ", align="R")
    pdf.ln()
    if invoice.get("tax", 0) > 0:
        pdf.cell(150, 8, "Tax:", align="R")
        pdf.cell(40, 8, f"${invoice.get('tax', 0):,.2f}  ", align="R")
        pdf.ln()
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(150, 10, "Total Due:", align="R")
    pdf.cell(40, 10, f"${invoice.get('total', 0):,.2f}  ", align="R")
    pdf.ln(14)

    # Status
    status = invoice.get("status", "draft").upper()
    if status == "PAID":
        pdf.set_text_color(0, 150, 0)
    elif status == "OVERDUE":
        pdf.set_text_color(200, 0, 0)
    else:
        pdf.set_text_color(100, 100, 100)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"STATUS: {status}", ln=True, align="C")
    pdf.set_text_color(0, 0, 0)

    # Notes
    if invoice.get("notes"):
        pdf.ln(6)
        pdf.set_font("Helvetica", "I", 10)
        pdf.multi_cell(0, 6, f"Notes: {invoice['notes']}")

    # Footer
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(130, 130, 130)
    pdf.cell(0, 6, "Thank you for your partnership with i'M On Social.", ln=True, align="C")

    filepath = os.path.join(PDF_DIR, f"{invoice_id}.pdf")
    pdf.output(filepath)
    return filepath


# ==================== INVOICE ENDPOINTS ====================

@router.post("/generate/{partner_id}")
async def generate_invoice(
    partner_id: str,
    body: dict = None,
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    """Manually generate an invoice for a partner. Body: { period: "YYYY-MM" }"""
    await _require_super_admin(x_user_id)
    body = body or {}
    period = body.get("period")
    if not period:
        now = datetime.now(timezone.utc)
        period = now.strftime("%Y-%m")
    invoice = await _generate_invoice_for_partner(partner_id, period, created_by=x_user_id)
    return invoice


@router.get("/list/{partner_id}")
async def list_invoices(partner_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """List all invoices for a partner."""
    await _require_super_admin(x_user_id)
    db = get_db()
    invoices = await db.partner_invoices.find(
        {"partner_id": partner_id}
    ).sort("created_at", -1).to_list(200)
    result = []
    for inv in invoices:
        result.append({
            "_id": str(inv["_id"]),
            "invoice_number": inv.get("invoice_number", ""),
            "period": inv.get("period", ""),
            "total": inv.get("total", 0),
            "status": inv.get("status", "draft"),
            "due_date": inv.get("due_date").isoformat() if isinstance(inv.get("due_date"), datetime) else inv.get("due_date"),
            "sent_at": inv.get("sent_at").isoformat() if isinstance(inv.get("sent_at"), datetime) else inv.get("sent_at"),
            "paid_at": inv.get("paid_at").isoformat() if isinstance(inv.get("paid_at"), datetime) else inv.get("paid_at"),
            "created_at": inv.get("created_at").isoformat() if isinstance(inv.get("created_at"), datetime) else inv.get("created_at"),
            "line_item_count": len(inv.get("line_items", [])),
        })
    return result


@router.get("/detail/{invoice_id}")
async def get_invoice_detail(invoice_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Get full invoice detail."""
    await _require_super_admin(x_user_id)
    db = get_db()
    inv = await db.partner_invoices.find_one({"_id": ObjectId(invoice_id)})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    inv["_id"] = str(inv["_id"])
    for key in ["period_start", "period_end", "due_date", "created_at", "sent_at", "paid_at"]:
        if isinstance(inv.get(key), datetime):
            inv[key] = inv[key].isoformat()
    return inv


@router.get("/pdf/{invoice_id}")
async def download_invoice_pdf(invoice_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Download invoice PDF."""
    await _require_super_admin(x_user_id)
    db = get_db()
    inv = await db.partner_invoices.find_one({"_id": ObjectId(invoice_id)}, {"pdf_path": 1, "invoice_number": 1})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    pdf_path = inv.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF not available")
    filename = f"{inv.get('invoice_number', 'invoice')}.pdf"
    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)


@router.patch("/status/{invoice_id}")
async def update_invoice_status(invoice_id: str, body: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Update invoice status (draft, sent, paid, overdue, cancelled)."""
    await _require_super_admin(x_user_id)
    db = get_db()
    status = body.get("status")
    valid = ["draft", "sent", "paid", "overdue", "cancelled"]
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid}")
    update = {"status": status}
    if status == "paid":
        update["paid_at"] = datetime.now(timezone.utc)
    if status == "sent":
        update["sent_at"] = datetime.now(timezone.utc)
    result = await db.partner_invoices.update_one({"_id": ObjectId(invoice_id)}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Regenerate PDF with updated status
    inv = await db.partner_invoices.find_one({"_id": ObjectId(invoice_id)})
    if inv:
        pdf_path = _generate_invoice_pdf(invoice_id, inv)
        await db.partner_invoices.update_one({"_id": ObjectId(invoice_id)}, {"$set": {"pdf_path": pdf_path}})

    return {"success": True, "status": status}


@router.post("/send/{invoice_id}")
async def send_invoice_email(invoice_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Send invoice to the partner via email."""
    await _require_super_admin(x_user_id)
    db = get_db()
    inv = await db.partner_invoices.find_one({"_id": ObjectId(invoice_id)})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    partner_email = inv.get("partner_email")
    if not partner_email:
        raise HTTPException(status_code=400, detail="No partner email on record")

    # Build email HTML
    period = inv.get("period", "")
    total = inv.get("total", 0)
    invoice_number = inv.get("invoice_number", "")
    partner_name = inv.get("partner_name", "Partner")
    due_date = inv.get("due_date")
    if isinstance(due_date, datetime):
        due_str = due_date.strftime("%B %d, %Y")
    else:
        due_str = str(due_date)[:10] if due_date else ""

    line_items_html = ""
    for item in inv.get("line_items", []):
        waiver_tag = ""
        if item.get("waived"):
            reason = item.get("waiver_reason", "Waived")
            waiver_tag = f' <span style="color:#888;font-style:italic;">({reason})</span>'
        line_items_html += f"""
        <tr>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;">{item.get('store_name','')}{waiver_tag}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center;">{item.get('billing_package','')}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right;">${item.get('rate',0):,.2f}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right;font-weight:600;">${item.get('amount',0):,.2f}</td>
        </tr>"""

    html_content = f"""
    <div style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif;">
        <h2 style="margin-bottom:4px;">Invoice {invoice_number}</h2>
        <p style="color:#666;margin-top:0;">Period: {period} | Due: {due_str}</p>
        <p>Hi {partner_name},</p>
        <p>Please find your monthly invoice below:</p>
        <table style="width:100%;border-collapse:collapse;margin:20px 0;">
            <thead>
                <tr style="background:#1e1e1e;color:#fff;">
                    <th style="padding:10px 12px;text-align:left;">Store / Account</th>
                    <th style="padding:10px 12px;text-align:center;">Package</th>
                    <th style="padding:10px 12px;text-align:right;">Rate</th>
                    <th style="padding:10px 12px;text-align:right;">Amount</th>
                </tr>
            </thead>
            <tbody>{line_items_html}</tbody>
        </table>
        <div style="text-align:right;margin-top:16px;">
            <p style="font-size:18px;font-weight:700;">Total Due: ${total:,.2f}</p>
        </div>
        <p style="color:#888;font-size:13px;margin-top:30px;">
            A downloadable PDF is available in your partner dashboard.
            If you have questions about this invoice, please contact support@imonsocial.com.
        </p>
    </div>
    """

    try:
        import resend
        resend_key = os.environ.get("RESEND_API_KEY")
        if not resend_key:
            raise HTTPException(status_code=500, detail="Email service not configured")
        resend.api_key = resend_key

        # Read PDF for attachment
        pdf_path = inv.get("pdf_path")
        attachments = []
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_data = f.read()
            import base64
            attachments = [{
                "filename": f"{invoice_number}.pdf",
                "content": list(pdf_data),
            }]

        params = {
            "from": "i'M On Social <billing@imonsocial.com>",
            "to": [partner_email],
            "reply_to": "support@imonsocial.com",
            "subject": f"Invoice {invoice_number} - {period}",
            "html": html_content,
        }
        if attachments:
            params["attachments"] = attachments

        import asyncio
        email_result = await asyncio.to_thread(resend.Emails.send, params)

        # Update invoice status to sent
        await db.partner_invoices.update_one(
            {"_id": ObjectId(invoice_id)},
            {"$set": {"status": "sent", "sent_at": datetime.now(timezone.utc)}}
        )

        return {"success": True, "email_id": email_result.get("id"), "sent_to": partner_email}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send invoice email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


@router.patch("/notes/{invoice_id}")
async def update_invoice_notes(invoice_id: str, body: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Update invoice notes."""
    await _require_super_admin(x_user_id)
    db = get_db()
    result = await db.partner_invoices.update_one(
        {"_id": ObjectId(invoice_id)},
        {"$set": {"notes": body.get("notes", "")}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"success": True}


# ==================== SCHEDULED MONTHLY GENERATION ====================

async def generate_monthly_invoices():
    """Called by the scheduler on the 1st of each month to generate invoices for all active partners."""
    db = get_db()
    now = datetime.now(timezone.utc)
    # Bill for the PREVIOUS month
    if now.month == 1:
        period = f"{now.year - 1}-12"
    else:
        period = f"{now.year}-{str(now.month - 1).zfill(2)}"

    partners = await db.white_label_partners.find(
        {"is_active": True, "billing_config.rate": {"$ne": None}},
    ).to_list(500)

    generated = 0
    errors = 0
    for partner in partners:
        pid = str(partner["_id"])
        try:
            # Check if invoice already exists
            existing = await db.partner_invoices.find_one({"partner_id": pid, "period": period})
            if existing:
                continue
            await _generate_invoice_for_partner(pid, period, created_by="system")
            generated += 1
            logger.info(f"[Billing] Generated invoice for partner {partner.get('name', pid)} - {period}")
        except Exception as e:
            errors += 1
            logger.error(f"[Billing] Failed to generate invoice for partner {pid}: {e}")

    logger.info(f"[Billing] Monthly invoice generation complete: {generated} generated, {errors} errors")
    return {"generated": generated, "errors": errors, "period": period}
