import json
import subprocess
from pathlib import Path
from time import time


BASE_DIR = Path(__file__).resolve().parent

TIME_STAMP = 0
CACHED_DATA = 1
_cache = {CACHED_DATA: None, TIME_STAMP: 0}
CACHE_TTL = 600

SWIFT_BINARY = f"{BASE_DIR}/mac/today_events"


def get_today_calendar_events():
    now = int(time())
    if _cache[CACHED_DATA] is not None and (now - _cache[TIME_STAMP] < CACHE_TTL):
        return _cache[CACHED_DATA]
    try:
        output = subprocess.check_output([SWIFT_BINARY], timeout=5)
        data = json.loads(output.decode() or "[]")
        _cache[CACHED_DATA] = data
        _cache[TIME_STAMP] = now
        return data
    except subprocess.TimeoutExpired:
        print("Calendar query timed out")
    except Exception as e:
        print("Calendar read error:", e)
    return []
