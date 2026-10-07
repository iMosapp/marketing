"""VIN hygiene: normalize what a camera or a thumb produced, then validate length, alphabet and the position-9 check digit."""
import re

ALPHABET = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
# OCR confusions: VINs never contain I, O or Q.
OCR_FIX = str.maketrans({"I": "1", "O": "0", "Q": "0"})
TRANSLIT = {**{c: i for i, c in enumerate("0123456789")},
            "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8, "J": 1, "K": 2, "L": 3, "M": 4, "N": 5,
            "P": 7, "R": 9, "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9}
WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]


def normalize(raw: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]", "", raw or "").upper()
    return s.translate(OCR_FIX)


def check_digit(vin: str) -> str:
    total = sum(TRANSLIT[c] * w for c, w in zip(vin, WEIGHTS))
    r = total % 11
    return "X" if r == 10 else str(r)


def north_american(vin: str) -> bool:
    return bool(vin) and vin[0] in "12345"


def validate(raw: str) -> dict:
    """{vin, valid, errors, checksum: ok|bad|n/a}. The checksum is binding for North American WMIs (1-5), advisory elsewhere."""
    vin = normalize(raw)
    errors = []
    if len(vin) != 17:
        errors.append(f"A VIN has 17 characters, this has {len(vin)}")
    bad = sorted({c for c in vin if c not in ALPHABET})
    if bad:
        errors.append("Not allowed in a VIN: " + ", ".join(bad))
    checksum = "n/a"
    if not errors:
        ok = check_digit(vin) == vin[8]
        if north_american(vin):
            checksum = "ok" if ok else "bad"
            if not ok:
                errors.append("Check digit does not match: one character is probably misread")
        else:
            checksum = "ok" if ok else "n/a"
    return {"vin": vin, "valid": not errors, "errors": errors, "checksum": checksum}


def candidates(text: str) -> list:
    """17-char VINs in OCR text, best first: whole tokens first, then windows inside longer runs, and only check-digit-verified
    windows when we have to slice (a random 17-char slice passes the check digit 1 time in 11)."""
    out = []
    tokens = [normalize(t) for t in re.findall(r"[A-Za-z0-9\-]+", text or "")]
    for t in tokens:
        if len(t) == 17 and validate(t)["valid"] and t not in out:
            out.append(t)
    for t in tokens:
        if len(t) > 17:
            for i in range(len(t) - 16):
                v = validate(t[i:i + 17])
                if v["valid"] and v["checksum"] == "ok" and v["vin"] not in out:
                    out.append(v["vin"])
    return out
