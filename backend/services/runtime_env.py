"""Where is this code running? Preview containers use the bundled local Mongo; production always gets a managed MONGO_URL.
Preview-only safety switches (SMS guard, widget ring dry-run, no number buying) must be inert anywhere else, because the
Deploy step copies backend/.env keys into the production environment."""
import os


def is_preview_runtime() -> bool:
    m = os.environ.get("MONGO_URL", "")
    return "localhost" in m or "127.0.0.1" in m
