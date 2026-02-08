"""
Flask views/routes for the irrigation control web interface.
Includes comprehensive error handling for hardware failures.
"""
import logging
import time
from datetime import datetime, timedelta
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    jsonify,
    flash,
)

from .config import NAMES, ZORDER, SENSOR_IP, SENSOR_TIMEOUT
from .hardware import (
    init_hardware,
    all_off,
    exclusive_on,
    get_all_hardware_status,
    HardwareError,
    GPIOError,
    ShellyError,
)
from .schedule_store import (
    load_schedules,
    save_schedules,
    get_recent_hardware_errors,
    log_hardware_error,
)
from .state import (
    state_lock,
    run_cancel,
    current_run,
    env_state,
    request_run_cancel,
    get_current_run,
    get_env_state,
    update_env_state,
)
from .sensor import EnvironmentSensor, SensorError, SensorTimeoutError

logger = logging.getLogger(__name__)

bp = Blueprint("main", __name__)

# Initialize sensor instance (with caching)
_sensor = EnvironmentSensor(SENSOR_IP, SENSOR_TIMEOUT, cache_duration=60)


# ============================================================================
# Helper Functions
# ============================================================================

def safe_hardware_operation(operation_func, device_id: str, operation_name: str):
    """
    Safely execute a hardware operation with error handling.
    
    Returns:
        Tuple of (success: bool, error_message: str or None)
    """
    try:
        operation_func()
        return True, None
    except GPIOError as e:
        error_msg = f"GPIO error on {device_id}: {str(e)}"
        logger.error(f"[VIEWS] {error_msg}")
        log_hardware_error(device_id, error_msg, "gpio")
        return False, f"GPIO device '{NAMES.get(device_id, device_id)}' is not responding"
    except ShellyError as e:
        error_msg = f"Shelly error on {device_id}: {str(e)}"
        logger.error(f"[VIEWS] {error_msg}")
        log_hardware_error(device_id, error_msg, "shelly")
        return False, f"Shelly device '{NAMES.get(device_id, device_id)}' is not responding"
    except HardwareError as e:
        error_msg = f"Hardware error on {device_id}: {str(e)}"
        logger.error(f"[VIEWS] {error_msg}")
        log_hardware_error(device_id, error_msg, "unknown")
        return False, f"Device '{NAMES.get(device_id, device_id)}' encountered an error"
    except Exception as e:
        error_msg = f"Unexpected error on {device_id}: {str(e)}"
        logger.exception(f"[VIEWS] {error_msg}")
        log_hardware_error(device_id, error_msg, "unexpected")
        return False, f"Unexpected error with '{NAMES.get(device_id, device_id)}'"


# ============================================================================
# Main UI Routes
# ============================================================================

@bp.route("/")
def index():
    """Main dashboard page."""
    try:
        scheds = load_schedules()
    except Exception as e:
        logger.error(f"[VIEWS] Error loading schedules: {e}")
        scheds = []

    # Compute latest "last_run" across schedules
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

    # Get current run state
    cr = get_current_run()
    formatted_current = {
        "active": cr.get("active", False),
        "name": cr.get("name"),
        "step": cr.get("step"),
        "ends": (
            cr["ends_at"].strftime("%H:%M:%S")
            if cr.get("ends_at")
            else "—"
        ),
    }

    # Get environment state
    env = get_env_state()

    # Current time for display
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Get hardware status for error display
    hw_status = get_all_hardware_status()
    failed_devices = [
        (device_id, NAMES.get(device_id, device_id))
        for device_id, status in hw_status.items()
        if status.get("is_failed", False)
    ]

    return render_template(
        "index.html",
        zones=[(k, NAMES.get(k, k)) for k in ZORDER],
        schedules=scheds,
        current=formatted_current,
        last_run=last_run,
        env=env,
        current_time=current_time,
        failed_devices=failed_devices,
    )


# ============================================================================
# Manual Control Routes
# ============================================================================

@bp.route("/on/<key>")
def on(key):
    """Turn on a specific zone."""
    try:
        devices = init_hardware()
        if key not in devices:
            logger.warning(f"[VIEWS] Unknown zone requested: {key}")
            return render_template(
                "error.html",
                error_title="Unknown Zone",
                error_message=f"Zone '{key}' does not exist.",
            ), 404

        success, error_msg = safe_hardware_operation(
            lambda: exclusive_on(key),
            key,
            "turn_on"
        )

        if not success:
            return render_template(
                "error.html",
                error_title="Hardware Error",
                error_message=error_msg,
                device_id=key,
            ), 500

        return redirect(url_for("main.index"))

    except Exception as e:
        logger.exception(f"[VIEWS] Unexpected error in /on/{key}")
        return render_template(
            "error.html",
            error_title="Unexpected Error",
            error_message="An unexpected error occurred. Please try again.",
        ), 500


@bp.route("/off/<key>")
def off(key):
    """Turn off a specific zone."""
    try:
        devices = init_hardware()
        if key not in devices:
            logger.warning(f"[VIEWS] Unknown zone requested: {key}")
            return render_template(
                "error.html",
                error_title="Unknown Zone",
                error_message=f"Zone '{key}' does not exist.",
            ), 404

        success, error_msg = safe_hardware_operation(
            lambda: devices[key].off(),
            key,
            "turn_off"
        )

        if not success:
            return render_template(
                "error.html",
                error_title="Hardware Error",
                error_message=error_msg,
                device_id=key,
            ), 500

        return redirect(url_for("main.index"))

    except Exception as e:
        logger.exception(f"[VIEWS] Unexpected error in /off/{key}")
        return render_template(
            "error.html",
            error_title="Unexpected Error",
            error_message="An unexpected error occurred. Please try again.",
        ), 500


@bp.route("/pulse/<key>", methods=["POST"])
def pulse(key):
    """Pulse a zone for a specific duration."""
    try:
        devices = init_hardware()
        if key not in devices:
            return render_template(
                "error.html",
                error_title="Unknown Zone",
                error_message=f"Zone '{key}' does not exist.",
            ), 404

        # Parse duration
        try:
            secs = float(request.form.get("secs", 5))
            secs = max(0, min(secs, 3600))  # Cap at 1 hour for safety
        except ValueError:
            return render_template(
                "error.html",
                error_title="Invalid Input",
                error_message="Duration must be a valid number.",
            ), 400

        # Turn on zone
        success, error_msg = safe_hardware_operation(
            lambda: exclusive_on(key),
            key,
            "pulse_on"
        )

        if not success:
            return render_template(
                "error.html",
                error_title="Hardware Error",
                error_message=error_msg,
                device_id=key,
            ), 500

        # Update state
        with state_lock:
            end = datetime.now() + timedelta(seconds=secs)
            current_run.update({
                "active": True,
                "name": f"Manual {NAMES.get(key, key)}",
                "step": f"{key}",
                "ends_at": end,
            })

        # Wait for duration
        time.sleep(secs)

        # Turn off zone
        success, error_msg = safe_hardware_operation(
            lambda: devices[key].off(),
            key,
            "pulse_off"
        )

        # Clear state regardless of success
        with state_lock:
            current_run.update({
                "active": False,
                "name": None,
                "step": None,
                "ends_at": None,
            })

        if not success:
            logger.warning(f"[VIEWS] Failed to turn off {key} after pulse")
            # Continue anyway - zone may have timed out

        return redirect(url_for("main.index"))

    except Exception as e:
        logger.exception(f"[VIEWS] Unexpected error in /pulse/{key}")
        # Try to clear state
        with state_lock:
            current_run.update({
                "active": False,
                "name": None,
                "step": None,
                "ends_at": None,
            })
        return render_template(
            "error.html",
            error_title="Unexpected Error",
            error_message="An unexpected error occurred during pulse operation.",
        ), 500


@bp.route("/all/off")
def all_off_route():
    """Turn off all zones and cancel any running schedule."""
    try:
        # Cancel any running schedule
        request_run_cancel()

        # Turn off all zones
        errors = []
        devices = init_hardware()
        for zone_id in devices:
            success, error_msg = safe_hardware_operation(
                lambda zid=zone_id: devices[zid].off(),
                zone_id,
                "all_off"
            )
            if not success:
                errors.append(error_msg)

        # Clear state
        with state_lock:
            current_run.update({
                "active": False,
                "name": None,
                "step": None,
                "ends_at": None,
            })

        if errors:
            logger.warning(f"[VIEWS] Some zones failed to turn off: {errors}")
            # Still redirect, but log the errors

        return redirect(url_for("main.index"))

    except Exception as e:
        logger.exception("[VIEWS] Unexpected error in /all/off")
        return render_template(
            "error.html",
            error_title="Error",
            error_message="Failed to turn off all zones. Some devices may still be active.",
        ), 500


# ============================================================================
# Schedule Management Routes
# ============================================================================

@bp.route("/schedules/add", methods=["POST"])
def add_schedule():
    """Add a new irrigation schedule."""
    def to_minutes(val):
        """Convert form value to integer minutes."""
        if val is None:
            return 0
        s = str(val).strip().replace(",", ".")
        if s == "":
            return 0
        try:
            f = float(s)
            return max(0, int(f))
        except Exception:
            return 0

    try:
        data = request.form
        name = (data.get("name") or "").strip()
        start = (data.get("start") or "").strip()
        
        # Greek day names to English
        day_mapping = {
            "Δευ": "Mon", "Τρι": "Tue", "Τετ": "Wed", "Πεμ": "Thu",
            "Παρ": "Fri", "Σαβ": "Sat", "Κυρ": "Sun"
        }
        
        days = []
        for d in data.getlist("days"):
            # Support both Greek and English day names
            if d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
                days.append(d)
            elif d in day_mapping:
                days.append(day_mapping[d])

        # Validate inputs
        if not name or not start:
            return render_template(
                "error.html",
                error_title="Missing Fields",
                error_message="Schedule name and start time are required.",
            ), 400

        if not days:
            return render_template(
                "error.html",
                error_title="Missing Fields",
                error_message="Please select at least one day of the week.",
            ), 400

        # Validate time format
        try:
            hour, minute = [int(x) for x in start.split(":")]
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except:
            return render_template(
                "error.html",
                error_title="Invalid Time",
                error_message="Start time must be in HH:MM format (24-hour).",
            ), 400

        # Build sequence (skip zones with 0 minutes)
        plan = []
        for z in ZORDER:
            mins = to_minutes(data.get(f"dur_{z}"))
            if mins > 0:
                plan.append({"key": z, "mins": mins})

        if not plan:
            return render_template(
                "error.html",
                error_title="No Zones Selected",
                error_message="Please set duration greater than 0 for at least one zone.",
            ), 400

        # Create schedule object
        scheds = load_schedules()
        max_id = max(
            (s.get("id", 0) for s in scheds if isinstance(s, dict)),
            default=0,
        )
        
        new_item = {
            "id": max_id + 1,
            "name": name,
            "start": start,
            "days": days,
            "sequence": plan,
            "created": int(time.time()),
        }
        
        scheds.append(new_item)
        
        # Save
        if not save_schedules(scheds):
            return render_template(
                "error.html",
                error_title="Save Failed",
                error_message="Failed to save schedule. Please try again.",
            ), 500

        logger.info(f"[VIEWS] Added new schedule: {name}")
        return redirect(url_for("main.index"))

    except Exception as e:
        logger.exception("[VIEWS] Error adding schedule")
        return render_template(
            "error.html",
            error_title="Error",
            error_message="An unexpected error occurred while adding the schedule.",
        ), 500


@bp.route("/schedules/del/<int:sid>")
def del_schedule(sid):
    """Delete a schedule by ID."""
    try:
        scheds = load_schedules()
        original_count = len(scheds)
        scheds = [s for s in scheds if s.get("id") != sid]
        
        if len(scheds) == original_count:
            logger.warning(f"[VIEWS] Attempted to delete non-existent schedule ID: {sid}")
        else:
            if not save_schedules(scheds):
                return render_template(
                    "error.html",
                    error_title="Delete Failed",
                    error_message="Failed to delete schedule. Please try again.",
                ), 500
            logger.info(f"[VIEWS] Deleted schedule ID: {sid}")

        return redirect(url_for("main.index"))

    except Exception as e:
        logger.exception(f"[VIEWS] Error deleting schedule {sid}")
        return render_template(
            "error.html",
            error_title="Error",
            error_message="An unexpected error occurred while deleting the schedule.",
        ), 500


# ============================================================================
# Environment Sensor Routes
# ============================================================================

@bp.route("/env/refresh")
def refresh_env():
    """Manually refresh sensor reading."""
    try:
        logger.info("[VIEWS] Manual sensor refresh requested")
        reading = _sensor.get_environment(use_cache=False)
        
        if reading:
            update_env_state(reading["temp"], reading["hum"])
            logger.info(
                f"[VIEWS] Sensor updated: temp={reading['temp']:.1f}°C, "
                f"hum={reading['hum']:.1f}%"
            )
        else:
            logger.warning("[VIEWS] Sensor refresh failed, keeping old values")
            # Could flash a message to user here if using flash messages

        return redirect(url_for("main.index"))

    except SensorTimeoutError:
        logger.error("[VIEWS] Sensor timeout during manual refresh")
        return render_template(
            "error.html",
            error_title="Sensor Timeout",
            error_message=f"The humidity sensor at {SENSOR_IP} did not respond. Please check the sensor connection.",
        ), 500

    except SensorError as e:
        logger.error(f"[VIEWS] Sensor error during manual refresh: {e}")
        return render_template(
            "error.html",
            error_title="Sensor Error",
            error_message=f"Error reading from humidity sensor: {str(e)}",
        ), 500

    except Exception as e:
        logger.exception("[VIEWS] Unexpected error during sensor refresh")
        return render_template(
            "error.html",
            error_title="Error",
            error_message="An unexpected error occurred while reading the sensor.",
        ), 500


# ============================================================================
# API Routes (for status monitoring)
# ============================================================================

@bp.route("/api/status")
def api_status():
    """Get system status as JSON."""
    try:
        return jsonify({
            "current_run": get_current_run(),
            "environment": get_env_state(),
            "hardware_status": get_all_hardware_status(),
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        logger.exception("[VIEWS] Error in /api/status")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/hardware_errors")
def api_hardware_errors():
    """Get recent hardware errors as JSON."""
    try:
        errors = get_recent_hardware_errors(limit=50)
        return jsonify({
            "errors": errors,
            "count": len(errors),
        })
    except Exception as e:
        logger.exception("[VIEWS] Error in /api/hardware_errors")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/sensor")
def api_sensor():
    """Get sensor status and reading."""
    try:
        status = _sensor.get_status()
        return jsonify(status)
    except Exception as e:
        logger.exception("[VIEWS] Error in /api/sensor")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Error Handlers
# ============================================================================

@bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return render_template(
        "error.html",
        error_title="Page Not Found",
        error_message="The requested page does not exist.",
    ), 404


@bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.exception("[VIEWS] Internal server error")
    return render_template(
        "error.html",
        error_title="Internal Server Error",
        error_message="An internal error occurred. Please try again later.",
    ), 500
