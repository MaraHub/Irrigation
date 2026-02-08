import json
import os
from datetime import datetime
from .config import SCHED_FILE
SKIP_LOG_FILE = os.path.join(os.path.dirname(SCHED_FILE), "skipped_runs.json")


def load_schedules():
    if not os.path.exists(SCHED_FILE):
        return []
    try:
        with open(SCHED_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def save_schedules(scheds):
    os.makedirs(os.path.dirname(SCHED_FILE), exist_ok=True)
    tmp = SCHED_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(scheds, f, indent=2)
    os.replace(tmp, SCHED_FILE)

def mark_last_run(sched, when_dt):
    sched["last_run"] = when_dt.strftime("%Y-%m-%d %H:%M")

def should_run_today(days_list, dt):
    map_days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    return map_days[dt.weekday()] in days_list

def time_matches(start_str, dt):
    try:
        h, m = [int(x) for x in start_str.split(":")]
        return dt.hour == h and dt.minute == m
    except:
        return False

def already_ran_this_minute(sched, dt):
    lr = sched.get("last_run")
    if not lr: return False
    try:
        prev = datetime.strptime(lr, "%Y-%m-%d %H:%M")
        return (prev.year,prev.month,prev.day,prev.hour,prev.minute) == (dt.year,dt.month,dt.day,dt.hour,dt.minute)
    except:
        return False

def log_skipped_run(sched, when_dt: datetime, humidity: float, temp: float | None):
    """
    Log a skipped irrigation run into a JSON log file and update the schedule
    with a 'last_skipped' summary.
    """
    record = {
        "time": when_dt.strftime("%Y-%m-%d %H:%M"),
        "schedule_id": sched.get("id"),
        "schedule_name": sched.get("name"),
        "humidity": float(humidity),
        "temp": float(temp) if temp is not None else None,
    }

    # Load existing log (if any)
    log = []
    try:
        if os.path.exists(SKIP_LOG_FILE):
            with open(SKIP_LOG_FILE, "r") as f:
                log = json.load(f)
    except Exception:
        log = []

    log.append(record)

    # Write atomically
    tmp = SKIP_LOG_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(log, f, indent=2)
    os.replace(tmp, SKIP_LOG_FILE)

    # Also store a compact summary on the schedule itself
    sched["last_skipped"] = {
        "time": record["time"],
        "humidity": record["humidity"],
        "temp": record["temp"],
    }
