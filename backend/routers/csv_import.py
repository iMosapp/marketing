"""
Contact Import router - parses Google Contacts CSV and Apple/Google VCF exports.
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
    """Strip formatting, return digits only. Prepend 1 for 10-digit US numbers."""
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
        # Fall back to the one marked 'pref' or just the first
        for p in phones:
            if 'pref' in p.get('_raw_type', '').lower():
                best = p
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


def _parse_birthday(raw: str) -> Optional[str]:
    """Parse birthday from various formats to ISO string."""
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    # Strip "value=date:" prefix from VCF
    raw = re.sub(r'^value=date:', '', raw, flags=re.IGNORECASE)
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y', '%d/%m/%Y'):
        try:
            dt = datetime.strptime(raw, fmt)
            # Skip bogus years (Google/Apple use 1604 when year unknown)
            if dt.year < 1900:
                return dt.replace(year=1900).isoformat()
            return dt.isoformat()
        except ValueError:
            continue
    return None


# ===================== CSV PARSER =====================

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


def _parse_csv_row(row: dict) -> dict:
    """Parse a single CSV row into a contact dict."""
    first_raw = row.get('First Name', '').strip()
    last_raw = row.get('Last Name', '').strip()
    org_name = row.get('Organization Name', '').strip()

    first_name, last_name = _split_name(first_raw, last_raw)

    phones = []
    for i in range(1, 5):
        label = row.get(f'Phone {i} - Label', '').strip()
        value = row.get(f'Phone {i} - Value', '').strip()
        if value:
            phones.append({'label': label or 'Other', 'value': value})

    emails_raw = []
    for i in range(1, 5):
        label = row.get(f'E-mail {i} - Label', '').strip()
        value = row.get(f'E-mail {i} - Value', '').strip()
        if value:
            emails_raw.append({'label': label or 'Other', 'value': value})

    primary_phone, all_phones = _pick_primary_phone(phones)
    primary_email, all_emails = _pick_primary_email(emails_raw)

    return {
        'first_name': first_name,
        'last_name': last_name,
        'organization_name': org_name or None,
        'phone': primary_phone,
        'email': primary_email or None,
        'phones': all_phones,
        'emails': all_emails,
        'employer': org_name or None,
        'occupation': row.get('Occupation', '').strip() or None,
        'address_street': row.get('Address 1 - Street', '').strip() or None,
        'address_city': row.get('Address 1 - City', '').strip() or None,
        'address_state': row.get('Address 1 - Region', '').strip() or None,
        'address_zip': row.get('Address 1 - Postal Code', '').strip() or None,
        'address_country': row.get('Address 1 - Country', '').strip() or None,
        'birthday': _parse_birthday(row.get('Birthday', '')),
        'notes': row.get('Notes', '').strip() or '',
    }


def parse_csv(text: str) -> list:
    """Parse a CSV string into a list of contact dicts."""
    reader = csv.DictReader(io.StringIO(text))
    contacts = []
    for row in reader:
        parsed = _parse_csv_row(row)
        if not parsed['phone'] and not parsed['email']:
            continue
        if not parsed['first_name'] and not parsed['last_name'] and not parsed['organization_name']:
            continue
        contacts.append(parsed)
    return contacts


# ===================== VCF PARSER =====================

def _extract_vcf_phone_label(type_str: str) -> str:
    """Extract a human-readable label from VCF TEL type string."""
    t = type_str.lower()
    if 'cell' in t or 'mobile' in t:
        return 'Mobile'
    if 'work' in t:
        return 'Work'
    if 'home' in t:
        return 'Home'
    if 'fax' in t:
        return 'Fax'
    return 'Other'


def _extract_vcf_email_label(type_str: str) -> str:
    """Extract a human-readable label from VCF EMAIL type string."""
    t = type_str.lower()
    if 'work' in t:
        return 'Work'
    if 'home' in t:
        return 'Home'
    return 'Personal'


def _parse_vcf_entry(lines: list) -> Optional[dict]:
    """Parse a single vCard entry (list of lines between BEGIN/END) into a contact dict."""
    phones = []
    emails_raw = []
    first_name = ''
    last_name = ''
    full_name = ''
    org_name = ''
    title = ''
    birthday = None
    notes = ''
    address = {}

    for line in lines:
        # Handle line continuations (lines starting with space/tab)
        line = line.strip()
        if not line:
            continue

        # Split into field and value — handle item1.TEL: prefix
        # Remove Apple-specific "item1." prefix
        field_line = re.sub(r'^item\d+\.', '', line)

        if ':' not in field_line:
            continue

        field_part, value = field_line.split(':', 1)
        value = value.strip()
        # Unescape VCF escapes
        value = value.replace('\\n', '\n').replace('\\,', ',').replace('\\;', ';')

        field_upper = field_part.upper()

        # Structured name: N:Last;First;Middle;Prefix;Suffix
        if field_upper.startswith('N') and (field_upper == 'N' or field_upper.startswith('N;')):
            parts = value.split(';')
            last_name = (parts[0] if len(parts) > 0 else '').strip()
            first_name = (parts[1] if len(parts) > 1 else '').strip()

        elif field_upper.startswith('FN'):
            full_name = value.strip()

        elif field_upper.startswith('ORG'):
            # ORG:Company Name; or ORG:Company Name\, Inc;
            org_name = value.rstrip(';').strip()

        elif field_upper.startswith('TITLE'):
            title = value.strip()

        elif field_upper.startswith('TEL'):
            raw_type = field_part
            label = _extract_vcf_phone_label(raw_type)
            # Clean the phone value (may have extensions like \;218)
            phone_val = value.split(';')[0].strip()
            if phone_val:
                phones.append({'label': label, 'value': phone_val, '_raw_type': raw_type})

        elif field_upper.startswith('EMAIL'):
            raw_type = field_part
            label = _extract_vcf_email_label(raw_type)
            if value:
                emails_raw.append({'label': label, 'value': value})

        elif field_upper.startswith('BDAY'):
            # BDAY:1975-06-26 or BDAY;value=date:1962-01-23
            bday_val = value
            if 'value=date' in field_part.lower():
                bday_val = value
            birthday = _parse_birthday(bday_val)

        elif field_upper.startswith('NOTE'):
            notes = value

        elif field_upper.startswith('ADR'):
            # ADR:PO Box;Extended;Street;City;State;ZIP;Country
            parts = value.split(';')
            street_parts = []
            if len(parts) > 0 and parts[0].strip():
                street_parts.append(parts[0].strip())  # PO Box
            if len(parts) > 2 and parts[2].strip():
                street_parts.append(parts[2].strip())  # Street
            if not address.get('street'):
                address['street'] = ', '.join(street_parts) if street_parts else None
                address['city'] = parts[3].strip() if len(parts) > 3 else None
                address['state'] = parts[4].strip() if len(parts) > 4 else None
                address['zip'] = parts[5].strip() if len(parts) > 5 else None
                address['country'] = parts[6].strip() if len(parts) > 6 else None

    # Fallback: if no structured name, split FN
    if not first_name and not last_name and full_name:
        parts = full_name.split()
        if len(parts) >= 2:
            first_name = parts[0]
            last_name = ' '.join(parts[1:])
        elif len(parts) == 1:
            first_name = parts[0]

    primary_phone, all_phones = _pick_primary_phone(phones)
    primary_email, all_emails = _pick_primary_email(emails_raw)

    if not primary_phone and not primary_email:
        return None
    if not first_name and not last_name and not org_name:
        return None

    return {
        'first_name': first_name,
        'last_name': last_name,
        'organization_name': org_name or None,
        'phone': primary_phone,
        'email': primary_email or None,
        'phones': all_phones,
        'emails': all_emails,
        'employer': org_name or None,
        'occupation': title or None,
        'address_street': address.get('street'),
        'address_city': address.get('city'),
        'address_state': address.get('state'),
        'address_zip': address.get('zip'),
        'address_country': address.get('country'),
        'birthday': birthday,
        'notes': notes or '',
    }


def parse_vcf(text: str) -> list:
    """Parse a VCF string into a list of contact dicts."""
    contacts = []
    current_entry = []
    in_card = False

    # Handle folded lines (continuation lines start with space/tab)
    unfolded_lines = []
    for line in text.splitlines():
        if line.startswith((' ', '\t')) and unfolded_lines:
            unfolded_lines[-1] += line.strip()
        else:
            unfolded_lines.append(line)

    for line in unfolded_lines:
        stripped = line.strip()
        if stripped.upper() == 'BEGIN:VCARD':
            in_card = True
            current_entry = []
        elif stripped.upper() == 'END:VCARD':
            if in_card and current_entry:
                parsed = _parse_vcf_entry(current_entry)
                if parsed:
                    contacts.append(parsed)
            in_card = False
            current_entry = []
        elif in_card:
            current_entry.append(stripped)

    return contacts


# ===================== SHARED DEDUP + ENDPOINTS =====================

async def _check_duplicates(user_id: str, contacts: list) -> tuple:
    """Check contacts against existing DB records. Returns (contacts_with_flags, stats)."""
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
    return contacts, new_count, dup_count


@router.post("/{user_id}/import-csv/preview")
async def preview_csv_import(user_id: str, file: UploadFile = File(...)):
    """Parse a CSV file and return a preview of contacts to import."""
    if not file.filename or not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Please upload a .csv file")

    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = content.decode('latin-1')

    contacts = parse_csv(text)
    skipped = len(list(csv.DictReader(io.StringIO(text)))) - len(contacts)
    contacts, new_count, dup_count = await _check_duplicates(user_id, contacts)

    return {
        "total_parsed": len(contacts),
        "new_contacts": new_count,
        "duplicates": dup_count,
        "skipped_no_info": max(skipped, 0),
        "source": "csv",
        "contacts": contacts
    }


@router.post("/{user_id}/import-vcf/preview")
async def preview_vcf_import(user_id: str, file: UploadFile = File(...)):
    """Parse a VCF/vCard file and return a preview of contacts to import."""
    fname = (file.filename or '').lower()
    if not fname.endswith('.vcf') and not fname.endswith('.vcard'):
        raise HTTPException(status_code=400, detail="Please upload a .vcf or .vcard file")

    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = content.decode('latin-1')

    # Count total vCards for skip stat
    total_vcards = text.upper().count('BEGIN:VCARD')
    contacts = parse_vcf(text)
    skipped = total_vcards - len(contacts)
    contacts, new_count, dup_count = await _check_duplicates(user_id, contacts)

    return {
        "total_parsed": len(contacts),
        "new_contacts": new_count,
        "duplicates": dup_count,
        "skipped_no_info": max(skipped, 0),
        "source": "vcf",
        "contacts": contacts
    }


@router.post("/{user_id}/import/preview")
async def preview_import(user_id: str, file: UploadFile = File(...)):
    """Auto-detect file type (CSV or VCF) and return a preview."""
    fname = (file.filename or '').lower()
    if fname.endswith('.vcf') or fname.endswith('.vcard'):
        return await preview_vcf_import(user_id, file)
    elif fname.endswith('.csv'):
        return await preview_csv_import(user_id, file)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Please upload a .csv or .vcf file.")


@router.post("/{user_id}/import-csv/confirm")
async def confirm_import(user_id: str, contacts: List[dict]):
    """Import the confirmed contacts. Works for both CSV and VCF previewed contacts."""
    db = get_db()
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
                base_filter = await get_data_filter(user_id)
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
            "occupation": c.get('occupation'),
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
