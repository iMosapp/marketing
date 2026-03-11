"""
Feature Permissions - Controls what menu items/features each user can access.
Supports section-level master toggles + individual item overrides.
Role-based templates provide tiered access: user < store_manager < org_admin < super_admin.
"""

# Base permissions for regular users (salespeople)
_USER_PERMISSIONS = {
    "my_tools": {
        "_enabled": True,
        "touchpoints": True,
        "ask_jessi": True,
        "training_hub": True,
        "team_chat": True,
    },
    "campaigns": {
        "_enabled": True,
        "campaign_builder": True,
        "campaign_dashboard": True,
        "broadcast": False,
        "date_triggers": True,
    },
    "content": {
        "_enabled": True,
        "sms_templates": True,
        "email_templates": True,
        "card_templates": False,
        "manage_showcase": True,
    },
    "insights": {
        "_enabled": True,
        "my_performance": True,
        "activity_reports": True,
        "email_analytics": True,
        "leaderboard": False,
        "lead_attribution": False,
    },
    "admin": {
        "_enabled": False,
    },
}

# Store Manager: user permissions + broadcast, card templates, leaderboard, and admin basics
_STORE_MANAGER_PERMISSIONS = {
    "my_tools": {
        "_enabled": True,
        "touchpoints": True,
        "ask_jessi": True,
        "training_hub": True,
        "team_chat": True,
    },
    "campaigns": {
        "_enabled": True,
        "campaign_builder": True,
        "campaign_dashboard": True,
        "broadcast": True,
        "date_triggers": True,
    },
    "content": {
        "_enabled": True,
        "sms_templates": True,
        "email_templates": True,
        "card_templates": True,
        "manage_showcase": True,
    },
    "insights": {
        "_enabled": True,
        "my_performance": True,
        "activity_reports": True,
        "email_analytics": True,
        "leaderboard": True,
        "lead_attribution": False,
    },
    "admin": {
        "_enabled": True,
        "users": True,
        "invite_team": True,
        "store_profile": True,
        "brand_kit": True,
        "admin_dashboard": False,
        "review_approvals": True,
        "showcase_approvals": True,
        "review_links": False,
        "contact_tags": True,
        "lead_sources": False,
        "integrations": False,
        "accounts": False,
    },
}

# Org Admin: manager permissions + lead attribution, admin dashboard, review links, lead sources, integrations, accounts
_ORG_ADMIN_PERMISSIONS = {
    "my_tools": {
        "_enabled": True,
        "touchpoints": True,
        "ask_jessi": True,
        "training_hub": True,
        "team_chat": True,
    },
    "campaigns": {
        "_enabled": True,
        "campaign_builder": True,
        "campaign_dashboard": True,
        "broadcast": True,
        "date_triggers": True,
    },
    "content": {
        "_enabled": True,
        "sms_templates": True,
        "email_templates": True,
        "card_templates": True,
        "manage_showcase": True,
    },
    "insights": {
        "_enabled": True,
        "my_performance": True,
        "activity_reports": True,
        "email_analytics": True,
        "leaderboard": True,
        "lead_attribution": True,
    },
    "admin": {
        "_enabled": True,
        "users": True,
        "invite_team": True,
        "store_profile": True,
        "brand_kit": True,
        "admin_dashboard": True,
        "review_approvals": True,
        "showcase_approvals": True,
        "review_links": True,
        "contact_tags": True,
        "lead_sources": True,
        "integrations": True,
        "accounts": True,
    },
}

# Super Admin: everything enabled (admin section handled by frontend role checks)
_SUPER_ADMIN_PERMISSIONS = {
    "my_tools": {
        "_enabled": True,
        "touchpoints": True,
        "ask_jessi": True,
        "training_hub": True,
        "team_chat": True,
    },
    "campaigns": {
        "_enabled": True,
        "campaign_builder": True,
        "campaign_dashboard": True,
        "broadcast": True,
        "date_triggers": True,
    },
    "content": {
        "_enabled": True,
        "sms_templates": True,
        "email_templates": True,
        "card_templates": True,
        "manage_showcase": True,
    },
    "insights": {
        "_enabled": True,
        "my_performance": True,
        "activity_reports": True,
        "email_analytics": True,
        "leaderboard": True,
        "lead_attribution": True,
    },
    "admin": {
        "_enabled": True,
        "users": True,
        "invite_team": True,
        "store_profile": True,
        "brand_kit": True,
        "admin_dashboard": True,
        "review_approvals": True,
        "showcase_approvals": True,
        "review_links": True,
        "contact_tags": True,
        "lead_sources": True,
        "integrations": True,
        "accounts": True,
    },
}

# Map role names to their permission templates
ROLE_PERMISSIONS = {
    "user": _USER_PERMISSIONS,
    "store_manager": _STORE_MANAGER_PERMISSIONS,
    "org_admin": _ORG_ADMIN_PERMISSIONS,
    "super_admin": _SUPER_ADMIN_PERMISSIONS,
}

# Default for backward compatibility (used when role is unknown)
DEFAULT_PERMISSIONS = _USER_PERMISSIONS


def get_role_defaults(role: str) -> dict:
    """Get the default permission template for a given role."""
    template = ROLE_PERMISSIONS.get(role, _USER_PERMISSIONS)
    return {k: dict(v) for k, v in template.items()}


def merge_permissions(user_perms: dict | None, role: str = "user") -> dict:
    """Merge user's saved permissions with role-based defaults.
    Missing keys get role-appropriate default values.
    User-specific overrides are preserved.
    """
    role_defaults = ROLE_PERMISSIONS.get(role, _USER_PERMISSIONS)

    if not user_perms:
        return {k: dict(v) for k, v in role_defaults.items()}

    merged = {}
    for section_key, defaults in role_defaults.items():
        user_section = user_perms.get(section_key, {})
        merged_section = {}
        for item_key, default_val in defaults.items():
            merged_section[item_key] = user_section.get(item_key, default_val)
        merged[section_key] = merged_section
    return merged


def is_feature_enabled(permissions: dict, section: str, item: str | None = None) -> bool:
    """Check if a feature is enabled for a user."""
    section_perms = permissions.get(section, {})
    if not section_perms.get("_enabled", True):
        return False
    if item is None:
        return True
    return section_perms.get(item, False)
