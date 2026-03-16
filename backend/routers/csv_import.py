"""
CSV Import router - parses Google Contacts CSV exports and imports contacts.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from bson import ObjectId
from datetime import datetime, timezone
from typing import List, Optional
import csv
import io
import re
import logging

from routers.database import get_db, get_data_filter

router = APIRouter(prefix="/contacts", tags=["Contacts"])
logger = logging.getLogger(__name__)

PHONE_LABEL_PRIORITY = ["mobile", "cell", "main", "work", "home", "other"]


def _normalize_phone(raw: str) -> str:
    """Strip formatting, return digits only. Prepend +1 for 10-digit US numbers."""
    digits = re.sub(r'\D', '', raw)
    if len(digits) == 10:
        digits = '1' + digits
    return digits


def _pick_primary_phone(phones: list) -> tuple:
    """Return (primary_number, all_phones_list). Picks by label priority."""
    if not phones:
        return '', []
    best = None
    for priority_label in PHONE_LABEL_PRIORITY:
        for p in phones:
            if priority_label in p['label'].lower():
                best = p
                break
        if best:
            break
    if not best:
        best = phones[0]
    return _normalize_phone(best['value']), [
        {'label': p['label'], 'value': _normalize_phone(p['value'])}
        for p in phones if p['value'].strip()
    ]


def _pick_primary_email(emails_list: list) -> tuple:
    """Return (primary_email, all_emails_list). Personal > Home > Work."""
    if not emails_list:
        return '', []
    priority = ["personal", "home", "other", "work"]
    best = None
    for pl in priority:
        for e in emails_list:
            if pl in e['label'].lower():
                best = e
                break
        if best:
            break
    if not best:
        best = emails_list[0]
    return best['value'].strip().lower(), [
        {'label': e['label'], 'value': e['value'].strip().lower()}
        for e in emails_list if e['value'].strip()
    ]


def _split_name(first_name_field: str, last_name_field: str) -> tuple:
    """Smart name splitting. Returns (first_name, last_name)."""
    first = (first_name_field or '').strip()
    last = (last_name_field or '').strip()
    if last:
        return first, last
    if not first:
        return '', ''
    parts = first.split()
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], ' '.join(parts[1:])


def _parse_birthday(raw: str) -> Optional[str]:
    """Parse birthday from Google CSV format (YYYY-MM-DD) to ISO string."""
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y', '%d/%m/%Y'):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.isoformat()
        except ValueError:
            continue
    return None


def _parse_row(row: dict) -> dict:
    """Parse a single CSV row into a contact dict."""
    first_raw = row.get('First Name', '').strip()
    last_raw = row.get('Last Name', '').strip()
    org_name = row.get('Organization Name', '').strip()

    first_name, last_name = _split_name(first_raw, last_raw)

    # Collect all phone numbers with labels
    phones = []
    for i in range(1, 5):
        label = row.get(f'Phone {i} - Label', '').strip()
        value = row.get(f'Phone {i} - Value', '').strip()
        if value:
            phones.append({'label': label or 'Other', 'value': value})

    # Collect all emails with labels
    emails_raw = []
    for i in range(1, 5):
        label = row.get(f'E-mail {i} - Label', '').strip()
        value = row.get(f'E-mail {i} - Value', '').strip()
        if value:
            emails_raw.append({'label': label or 'Other', 'value': value})

    primary_phone, all_phones = _pick_primary_phone(phones)
    primary_email, all_emails = _pick_primary_email(emails_raw)

    # Address (use Address 1)
    address_street = row.get('Address 1 - Street', '').strip()
    address_city = row.get('Address 1 - City', '').strip()
    address_state = row.get('Address 1 - Region', '').strip()
    address_zip = row.get('Address 1 - Postal Code', '').strip()
    address_country = row.get('Address 1 - Country', '').strip()

    birthday = _parse_birthday(row.get('Birthday', ''))
    notes = row.get('Notes', '').strip()

    return {
        'first_name': first_name,
        'last_name': last_name,
        'organization_name': org_name or None,
        'phone': primary_phone,
        'email': primary_email or None,
        'phones': all_phones,
        'emails': all_emails,
        'employer': org_name or None,
        'address_street': address_street or None,
        'address_city': address_city or None,
        'address_state': address_state or None,
        'address_zip': address_zip or None,
        'address_country': address_country or None,
        'birthday': birthday,
        'notes': notes or None,
    }


@router.post("/{user_id}/import-csv/preview")
async def preview_csv_import(user_id: str, file: UploadFile = File(...)):
    """Parse a Google Contacts CSV and return a preview of what will be imported."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Please upload a .csv file")

    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = content.decode('latin-1')

    reader = csv.DictReader(io.StringIO(text))
    contacts = []
    skipped = 0

    for row in reader:
        parsed = _parse_row(row)
        if not parsed['phone'] and not parsed['email']:
            skipped += 1
            continue
        if not parsed['first_name'] and not parsed['last_name'] and not parsed['organization_name']:
            skipped += 1
            continue
        contacts.append(parsed)

    # Check for duplicates against existing contacts
    db = get_db()
    base_filter = await get_data_filter(user_id)
    existing_phones = set()
    existing_emails = set()

    cursor = db.contacts.find(base_filter, {"phone": 1, "email": 1})
    async for doc in cursor:
        p = doc.get('phone', '')
        if p:
            clean = re.sub(r'\D', '', p)
            if len(clean) >= 7:
                existing_phones.add(clean[-7:])
        e = doc.get('email', '')
        if e:
            existing_emails.add(e.strip().lower())

    for c in contacts:
        c['is_duplicate'] = False
        if c['phone']:
            suffix = re.sub(r'\D', '', c['phone'])[-7:]
            if suffix in existing_phones:
                c['is_duplicate'] = True
        if c['email'] and c['email'].lower() in existing_emails:
            c['is_duplicate'] = True

    new_count = sum(1 for c in contacts if not c['is_duplicate'])
    dup_count = sum(1 for c in contacts if c['is_duplicate'])

    return {
        "total_parsed": len(contacts),
        "new_contacts": new_count,
        "duplicates": dup_count,
        "skipped_no_info": skipped,
        "contacts": contacts
    }


@router.post("/{user_id}/import-csv/confirm")
async def confirm_csv_import(user_id: str, contacts: List[dict]):
    """Import the confirmed contacts from CSV preview."""
    db = get_db()
    base_filter = await get_data_filter(user_id)
    imported = 0
    skipped = 0

    for c in contacts:
        if c.get('is_duplicate'):
            skipped += 1
            continue

        phone = c.get('phone', '')
        if phone:
            suffix = re.sub(r'\D', '', phone)
            if len(suffix) >= 7:
                existing = await db.contacts.find_one({
                    **base_filter,
                    "phone": {"$regex": suffix[-7:] + "$"}
                })
                if existing:
                    skipped += 1
                    continue

        now = datetime.now(timezone.utc)
        birthday = None
        if c.get('birthday'):
            try:
                birthday = datetime.fromisoformat(c['birthday'])
            except (ValueError, TypeError):
                pass

        contact_doc = {
            "user_id": user_id,
            "original_user_id": user_id,
            "first_name": c.get('first_name', ''),
            "last_name": c.get('last_name', ''),
            "organization_name": c.get('organization_name'),
            "phone": phone,
            "email": c.get('email'),
            "phones": c.get('phones', []),
            "emails": c.get('emails', []),
            "employer": c.get('employer'),
            "address_street": c.get('address_street'),
            "address_city": c.get('address_city'),
            "address_state": c.get('address_state'),
            "address_zip": c.get('address_zip'),
            "address_country": c.get('address_country'),
            "birthday": birthday,
            "notes": c.get('notes') or "",
            "tags": ["csv-import"],
            "source": "csv",
            "ownership_type": "personal",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }

        await db.contacts.insert_one(contact_doc)
        imported += 1

    return {
        "imported": imported,
        "skipped": skipped,
        "total": len(contacts)
    }
