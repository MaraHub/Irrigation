# waterapp/views.py
from datetime import datetime, timedelta
import time

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    jsonify,
)

from .config import NAMES, ZORDER, SENSOR_IP
from .hardware import init_hardware, all_off, exclusive_on
from .schedule_store import load_schedules, save_schedules
from .state import state_lock, run_cancel, current_run, env_state
from .sensor import get_environment



bp = Blueprint("main", __name__)


# Basic actions (local helpers)

def set_on(key: str) -> None:
    exclusive_on(key)


def set_off(key: str) -> None:
    init_hardware()[key].off()


#
#  Routes – UI & API
#
@bp.route("/")
def index():
    scheds = load_schedules()

    # compute latest "last_run" across schedules
    last_run = None
    latest_dt = None
    for s in scheds:
        lr = s.get("last_run")
        if not lr:
            continue
        try:
            dt = datetime.strptime(lr, "%Y-%m-%d %H:%M")
        except Exception:
            continue
        if latest_dt is None or dt > latest_dt:
            latest_dt = dt
            last_run = f'{s.get("name", "?")} — {lr}'

    # snapshot of current run state
    with state_lock:
        cr = {
            "active": bool(current_run.get("active")),
            "name": current_run.get("name"),
            "step": current_run.get("step"),
            "ends": (
                current_run["ends_at"].strftime("%H:%M:%S")
                if current_run.get("ends_at")
                else "—"
            ),
        }
        env=dict(env_state)
    
    # current time for display (up to minutes)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")


    return render_template(
        "index.html",
        zones=[(k, NAMES.get(k, k)) for k in ZORDER],
        schedules=scheds,
        current=cr,
        last_run=last_run,
        env=env,
        current_time=current_time,
    )


@bp.route("/on/<key>")
def on(key):
    if key not in init_hardware():
        return ("Unknown relay", 404)
    with state_lock:
        set_on(key)
    return redirect(url_for("main.index"))


@bp.route("/off/<key>")
def off(key):
    if key not in init_hardware():
        return ("Unknown relay", 404)
    with state_lock:
        set_off(key)
    return redirect(url_for("main.index"))


@bp.route("/pulse/<key>", methods=["POST"])
def pulse(key):
    if key not in init_hardware():
        return ("Unknown relay", 404)

    secs = float(request.form.get("secs", 5))
    if secs < 0:
        secs = 0

    with state_lock:
        # turn only this zone on
        exclusive_on(key)
        end = datetime.now() + timedelta(seconds=secs)
        current_run.update(
            {
                "active": True,
                "name": f"Manual {key}",
                "step": f"{key}",
                "ends_at": end,
            }
        )

    time.sleep(secs)

    with state_lock:
        init_hardware()[key].off()
        current_run.update(
            {"active": False, "name": None, "step": None, "ends_at": None}
        )

    return redirect(url_for("main.index"))


@bp.route("/all/off")
def all_off_route():
    # also cancel any running schedule
    run_cancel.set()
    with state_lock:
        all_off()
        current_run.update(
            {"active": False, "name": None, "step": None, "ends_at": None}
        )
    return redirect(url_for("main.index"))


@bp.route("/api/relays")
def api_relays():
    devs = init_hardware()
    return jsonify({k: int(devs[k].value) for k in devs})


# 
#  Schedules – add/delete

@bp.route("/schedules/add", methods=["POST"])
def add_schedule():
    def to_minutes(val):
        if val is None:
            return 0
        s = str(val).strip().replace(",", ".")
        if s == "":
            return 0
        try:
            f = float(s)
            if f < 0:
                return 0
            return int(f)
        except Exception:
            return 0

    data = request.form
    name = (data.get("name") or "").strip()
    start = (data.get("start") or "").strip()
    days = [
        d
        for d in data.getlist("days")
        if d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    ]

    if not name or not start:
        return ("Missing fields: need name and start (HH:MM).", 400)
    if not days:
        return ("Missing fields: need at least one day (Mon–Sun).", 400)

    # build plan in fixed order, skip 0 minutes
    plan = []
    for z in ZORDER:
        mins = to_minutes(data.get(f"dur_{z}"))
        if mins > 0:
            plan.append({"key": z, "mins": mins})

    if not plan:
        return ("Missing fields: need at least one zone with minutes > 0.", 400)

    # build schedule object that UI & scheduler expect
    scheds = load_schedules()
    max_id = max(
        (s.get("id", 0) for s in scheds if isinstance(s, dict)),
        default=0,
    )
    new_item = {
        "id": max_id + 1,
        "name": name,
        "start": start,     # "HH:MM"
        "days": days,       # ["Mon","Tue",...]
        "sequence": plan,   # [{"key":"R1","mins":5}, ...]
        "created": int(time.time()),
    }
    scheds.append(new_item)
    save_schedules(scheds)
    return redirect(url_for("main.index"))


@bp.route("/schedules/del/<int:sid>")
def del_schedule(sid):
    scheds = load_schedules()
    scheds = [s for s in scheds if s.get("id") != sid]
    save_schedules(scheds)
    return redirect(url_for("main.index"))

@bp.route("/env/refresh")
def refresh_env():
    """Manually refresh sensor reading for the UI."""
    reading = get_environment(SENSOR_IP)
    with state_lock:
        if reading:
            env_state["temp"] = reading["temp"]
            env_state["hum"] = reading["hum"]
        # if reading failed, we just keep the old values

    return redirect(url_for("main.index"))
