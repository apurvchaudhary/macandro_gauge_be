import json
import subprocess
from datetime import datetime
from pathlib import Path
from time import time

BASE_DIR = Path(__file__).resolve().parent

# Simple per-date cache
# [date_key] = {"data": [...], "ts": epoch_seconds}
_cache: dict[str, dict] = {}
CACHE_TTL = 600

SWIFT_BINARY = f"{BASE_DIR}/mac/today_events"


def _now() -> int:
    return int(time())


def _date_key(date_str: str | None) -> str:
    # Normalizes to YYYY-MM-DD (local time). If None -> today.
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        # accept an already-correct format; validate by parsing
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        # fallback to today on bad format
        return datetime.now().strftime("%Y-%m-%d")


def get_calendar_events(date_str: str | None = None):
    """Return calendar events for the given date (YYYY-MM-DD).

    If date_str is None or invalid, defaults today. Results are cached per date
    for CACHE_TTL seconds. Each event includes a scheduler (calendar) name.
    """
    key = _date_key(date_str)
    now = _now()
    if (c := _cache.get(key)) and now - c.get("ts", 0) < CACHE_TTL:
        return c.get("data", [])

    cmd = [SWIFT_BINARY]
    if date_str:
        # pass the original string; Swift side validates/uses today if invalid
        cmd.append(date_str)
    try:
        output = subprocess.check_output(cmd, timeout=7)
        data = json.loads(output.decode() or "[]")
        _cache[key] = {"data": data, "ts": now}
        return data
    except subprocess.TimeoutExpired:
        print("Calendar query timed out")
    except Exception as e:
        print("Calendar read error:", e)
    return []


def get_today_calendar_events():
    return get_calendar_events(None)
