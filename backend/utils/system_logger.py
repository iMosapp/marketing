"""
System-level logging to MongoDB.
Stores warnings and errors in `system_logs` so they can be reviewed
from the admin panel without needing server access.

Usage:
    from utils.system_logger import syslog
    await syslog.error("ai_reply", "GPT call failed", error=e, user_id=user_id)
    await syslog.warning("twilio", "SMS send failed", detail=str(e))
    await syslog.info("voice", "Recording transcribed", contact=name)
"""
from datetime import datetime
import logging
import os
import traceback

logger = logging.getLogger(__name__)


class SystemLogger:
    def __init__(self):
        self._db = None

    def _get_db(self):
        if self._db is None:
            from routers.database import get_db
            self._db = get_db()
        return self._db

    async def _write(self, level: str, category: str, message: str, **kwargs):
        """Write a log entry to MongoDB system_logs collection."""
        try:
            db = self._get_db()
            entry = {
                "level":     level,
                "category":  category,
                "message":   message,
                "timestamp": datetime.utcnow(),
                **{k: str(v)[:500] if v is not None else None for k, v in kwargs.items()},
            }
            await db.system_logs.insert_one(entry)
        except Exception:
            pass  # Never let logging crash the app

    async def error(self, category: str, message: str, error: Exception = None, **kwargs):
        tb = traceback.format_exc() if error else None
        logger.error(f"[{category.upper()}] {message}: {error}")
        await self._write(
            "error", category, message,
            error_type=type(error).__name__ if error else None,
            error_detail=str(error)[:500] if error else None,
            traceback=tb[:1000] if tb and tb != "NoneType: None\n" else None,
            **kwargs
        )

    async def warning(self, category: str, message: str, **kwargs):
        logger.warning(f"[{category.upper()}] {message}")
        await self._write("warning", category, message, **kwargs)

    async def info(self, category: str, message: str, **kwargs):
        logger.info(f"[{category.upper()}] {message}")
        await self._write("info", category, message, **kwargs)


# Singleton — import this everywhere
syslog = SystemLogger()
