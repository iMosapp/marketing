"""Company Docs access rules shared by the docs router and AI retrieval: which documents are super-admin-only and what counts as a leaked credential."""
import re

# Internal engineering, operations, architecture, tech-stack and working-log documents: super admins only. Legal, policy, training, security and integrations stay admin-wide.
RESTRICTED_CATEGORIES = frozenset({"prd", "operations"})

WITHHELD_NOTE = ("# Document withheld\n\nThis document was not published: the sync found text that looks like a credential in the source file. "
                 "Remove the value from the repository file and redeploy.")

CREDENTIAL_PATTERNS = [
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}\s*/\s*(?=\S*\d)(?=\S*[!@#$%^&*])\S{6,}"),  # email / Passw0rd!
    re.compile(r"(?i)\bpassword\b[\"']?\s*[:=]\s*[\"']?(?=\S*\d)(?=\S*[!@#$%^&*])[A-Za-z0-9!@#$%^&*]{6,}"),
    re.compile(r"mongodb(\+srv)?://[^\s/@]+:[^\s/@]+@"),
    re.compile(r"\b[sr]k_(live|test)_[A-Za-z0-9]{16,}"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bwhsec_[A-Za-z0-9]{16,}"),
    re.compile(r"\bre_[A-Za-z0-9]{8,}_[A-Za-z0-9]{16,}"),
    re.compile(r"\bAC[0-9a-f]{32}\b"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
]


def is_restricted(doc: dict) -> bool:
    return doc.get("required_role") == "super_admin" or doc.get("category") in RESTRICTED_CATEGORIES


def credential_hits(text: str) -> int:
    """How many credential-looking values a text contains. Never returns the values."""
    return sum(len(p.findall(text or "")) for p in CREDENTIAL_PATTERNS)
