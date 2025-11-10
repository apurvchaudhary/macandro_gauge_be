import time
from collections import deque
from typing import Optional

import psutil
from flask import Flask, jsonify, request

from scheduler import get_today_calendar_events, get_calendar_events

app = Flask(__name__)

# --- Network throughput state (to compute delta/sec) ---
_prev_net_bytes: Optional[int] = None
_prev_time: Optional[float] = None

# Assume a nominal max link speed to map Mbps to 0-100 gauge range.
# If your link is faster/slower, adjust this value.
ASSUMED_MAX_LINK_MBPS = 300.0

# store recent Mbps samples for smoothing
_last_values = deque(maxlen=5)


# noinspection PyBroadException
def _safe_psutil_call(func, default):
    try:
        return func()
    except Exception:
        return default


def get_cpu_percent() -> float:
    """Return CPU utilization percent (0-100)."""
    if psutil is None:
        return 0.0
    # psutil.cpu_percent with interval=0 returns the last computed value; per=per-cpu not needed.
    return float(_safe_psutil_call(lambda: psutil.cpu_percent(interval=0.0), 0.0))


def get_mem_percent() -> float:
    """Return Memory utilization percent (0-100)."""
    if psutil is None:
        return 0.0
    return float(_safe_psutil_call(lambda: psutil.virtual_memory().percent, 0.0))


def get_net_gauge_value() -> float:
    """Return smoothed network usage as a percentage of 300 Mbps link."""
    global _prev_net_bytes, _prev_time

    io = _safe_psutil_call(lambda: psutil.net_io_counters(), None)
    if io is None:
        return 0.0

    total_bytes = io.bytes_sent + io.bytes_recv
    now = time.time()

    if _prev_net_bytes is None or _prev_time is None:
        _prev_net_bytes = total_bytes
        _prev_time = now
        return 0.0

    # compute delta bytes/sec
    dt = max(1e-6, now - _prev_time)
    dbytes = max(0, total_bytes - _prev_net_bytes)

    _prev_net_bytes = total_bytes
    _prev_time = now

    mbps = (dbytes * 8.0) / dt / 1_000_000.0  # bytes/sec → Mbps

    # smoothing (5-sample moving average)
    _last_values.append(mbps)
    smoothed = sum(_last_values) / len(_last_values)

    # convert to gauge % of your link capacity
    pct = (smoothed / ASSUMED_MAX_LINK_MBPS) * 100.0

    # clamp 0–100
    return round(max(0.0, min(100.0, pct)), 2)


def get_battery_percent() -> float:
    """Return battery percentage (0-100). If unavailable, return 0."""
    if psutil is None:
        return 0.0
    batt = _safe_psutil_call(lambda: psutil.sensors_battery(), None)
    if not batt or batt.percent is None:
        return 0.0
    return float(max(0.0, min(100.0, batt.percent)))


@app.get("/stats")
def stats():
    """Provide the metrics expected by the Kivy app sample.

    Keys expected (per provided sample):
      - cpu:    CPU usage percent (0-100)
      - mem:    Memory usage percent (0-100)
      - net:    Network gauge value (0-100) based on recent throughput
      - power:  Battery percent (0-100), 0 if not available
    """
    data = {
        "cpu": get_cpu_percent(),
        "mem": get_mem_percent(),
        "net": get_net_gauge_value(),
        "power": get_battery_percent(),
        "events": get_today_calendar_events()
    }
    return jsonify(data)


@app.get("/events")
def events():
    """
    Return calendar events for a given date.

    Query params:
      - date: optional, format YYYY-MM-DD. Defaults to today if omitted or invalid.
    Response: JSON array of events with fields: title, location, from, to, scheduler
    """
    date = request.args.get("date")
    events_data = get_calendar_events(date)
    return jsonify(events_data)


if __name__ == "__main__":
    # Run on all interfaces so a device on the same network can reach it.
    # The Kivy sample uses http://<server-ip>:8001/stats
    app.run(host="0.0.0.0", port=8001, debug=False)
