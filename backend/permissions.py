"""
Feature Permissions - Controls what menu items/features each user can access.
Supports section-level master toggles + individual item overrides.
"""

# Default permissions for new users (Progressive disclosure - core ON, advanced OFF)
DEFAULT_PERMISSIONS = {
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
        "date_triggers": False,
    },
    "content": {
        "_enabled": True,
        "sms_templates": True,
        "email_templates": True,
        "card_templates": False,
        "manage_showcase": False,
    },
    "insights": {
        "_enabled": True,
        "my_performance": True,
        "activity_reports": False,
        "email_analytics": False,
        "leaderboard": False,
        "lead_attribution": False,
    },
}


def merge_permissions(user_perms: dict | None) -> dict:
    """Merge user's saved permissions with defaults. Missing keys get default values."""
    if not user_perms:
        return {k: dict(v) for k, v in DEFAULT_PERMISSIONS.items()}

    merged = {}
    for section_key, defaults in DEFAULT_PERMISSIONS.items():
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
