"""Where is this code running? Preview containers use the bundled local Mongo; production always gets a managed MONGO_URL.
Preview-only safety switches (SMS guard, widget ring dry-run, no number buying) must be inert anywhere else, because the
Deploy step copies backend/.env keys into the production environment."""
import os


def is_preview_runtime() -> bool:
    m = os.environ.get("MONGO_URL", "")
    return "localhost" in m or "127.0.0.1" in m


TRUTHY = ("1", "true", "yes", "on")


def preview_flag(name: str) -> bool:
    """A preview-only switch: honoured only in the preview runtime, whatever value the Deploy step copied into production."""
    return is_preview_runtime() and (os.environ.get(name) or "").strip().lower() in TRUTHY


def opt_in_flag(name: str) -> bool:
    """A flag that may run in production, but there only with the literal value `production` (set on purpose in Secrets); preview honours the usual truthy values."""
    v = (os.environ.get(name) or "").strip().lower()
    return v == "production" or (is_preview_runtime() and v in TRUTHY)
