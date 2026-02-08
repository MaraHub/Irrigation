"""
Background scheduler for automated irrigation runs.
Checks schedules periodically and executes them with error handling.
"""
import logging
import time
import traceback
from datetime import datetime, timedelta
from threading import Thread

from .config import CHECK_INTERVAL_SEC, SENSOR_IP, HUMIDITY_SKIP_THRESHOLD
from .hardware import all_off, exclusive_on, init_hardware, HardwareError
from .schedule_store import (
    load_schedules,
    save_schedules,
    mark_last_run,
    should_run_today,
    time_matches,
    already_ran_this_minute,
    log_skipped_run,
    log_hardware_error,
)
from .state import (
    state_lock,
    run_cancel,
    current_run,
    is_cancel_requested,
    clear_run_cancel,
    set_current_run,
)
from .sensor import EnvironmentSensor, SensorError

logger = logging.getLogger(__name__)

# Sensor instance for scheduler
_sensor = EnvironmentSensor(SENSOR_IP, timeout=10.0, cache_duration=300)  # 5min cache


def run_sequence(sched: dict):
    """
    Execute an irrigation sequence.
    
    Args:
        sched: Schedule dictionary with 'name' and 'sequence' fields
    """
    name = sched["name"]
    seq = sched["sequence"]
    sched_id = sched.get("id")
    
    logger.info(f"[SCHEDULER] Starting sequence: {name}")
    clear_run_cancel()

    # Mark as starting
    set_current_run(
        active=True,
        name=name,
        step="starting",
        ends_at=None,
        schedule_id=sched_id
    )

    try:
        # Initialize hardware
        devices = init_hardware()
        
        # Calculate total duration
        total_secs = sum(max(0, z.get("mins", 0)) * 60 for z in seq)
        end_time = datetime.now() + timedelta(seconds=total_secs)
        
        logger.info(f"[SCHEDULER] Sequence will run for {total_secs}s (until {end_time.strftime('%H:%M:%S')})")
        
        # Update with end time
        set_current_run(
            active=True,
            name=name,
            step="starting",
            ends_at=end_time,
            schedule_id=sched_id
        )

        # Execute each step in sequence
        for i, zone_config in enumerate(seq, start=1):
            key = zone_config.get("key")
            mins = max(0, int(zone_config.get("mins", 0)))
            
            if not key or mins == 0:
                logger.warning(f"[SCHEDULER] Skipping invalid step: {zone_config}")
                continue

            zone_name = key  # Could look up in NAMES dict if needed
            logger.info(f"[SCHEDULER] Step {i}/{len(seq)}: {key} for {mins} minutes")

            # Update state
            set_current_run(
                active=True,
                name=name,
                step=f"{i}/{len(seq)}: {key} ({mins}m)",
                ends_at=end_time,
                schedule_id=sched_id
            )

            # Turn on zone with error handling
            try:
                exclusive_on(key)
            except HardwareError as e:
                error_msg = f"Failed to activate zone {key}"
                logger.error(f"[SCHEDULER] {error_msg}: {e}")
                log_hardware_error(key, str(e), "activation_failed")
                
                # Continue with next zone instead of aborting entire sequence
                logger.warning(f"[SCHEDULER] Continuing to next zone after error")
                continue
            except Exception as e:
                error_msg = f"Unexpected error activating zone {key}"
                logger.exception(f"[SCHEDULER] {error_msg}")
                log_hardware_error(key, str(e), "unexpected")
                continue

            # Wait for the specified duration
            remaining = mins * 60
            check_interval = 1.0  # Check cancel every second
            
            while remaining > 0:
                # Check for cancellation
                if is_cancel_requested():
                    logger.info(f"[SCHEDULER] Cancellation requested during {key}")
                    raise KeyboardInterrupt("Run cancelled by user")
                
                # Sleep in small increments to allow cancellation
                sleep_time = min(check_interval, remaining)
                time.sleep(sleep_time)
                remaining -= sleep_time

            # Turn off this zone before moving to next
            try:
                devices[key].off()
                logger.info(f"[SCHEDULER] Turned off {key}")
            except Exception as e:
                error_msg = f"Failed to turn off zone {key}"
                logger.error(f"[SCHEDULER] {error_msg}: {e}")
                log_hardware_error(key, str(e), "deactivation_failed")
                # Continue anyway

        # Sequence completed successfully
        logger.info(f"[SCHEDULER] Sequence '{name}' completed successfully")
        set_current_run(active=False, name=None, step=None, ends_at=None)

    except KeyboardInterrupt:
        # User cancelled the run
        logger.info(f"[SCHEDULER] Sequence '{name}' cancelled by user")
        try:
            all_off()
        except Exception as e:
            logger.error(f"[SCHEDULER] Error turning off zones during cancel: {e}")
        
        set_current_run(active=False, name=None, step="cancelled", ends_at=None)

    except Exception as e:
        # Unexpected error during sequence
        logger.exception(f"[SCHEDULER] Unexpected error in sequence '{name}'")
        
        # Try to turn off all zones
        try:
            all_off()
        except Exception as off_error:
            logger.error(f"[SCHEDULER] Error turning off zones after error: {off_error}")
        
        set_current_run(active=False, name=None, step="error", ends_at=None)


def scheduler_loop():
    """
    Main scheduler loop. Runs continuously checking for schedules to execute.
    """
    logger.info("[SCHEDULER] Started scheduler loop")
    
    while True:
        try:
            now = datetime.now()
            
            # Load current schedules
            try:
                scheds = load_schedules()
            except Exception as e:
                logger.error(f"[SCHEDULER] Error loading schedules: {e}")
                time.sleep(CHECK_INTERVAL_SEC)
                continue

            # Check each schedule
            for sched in scheds:
                try:
                    # Check if schedule should run now
                    should_run = (
                        should_run_today(sched.get("days", []), now) and
                        time_matches(sched.get("start", ""), now) and
                        not already_ran_this_minute(sched, now)
                    )
                    
                    if not should_run:
                        continue

                    logger.info(f"[SCHEDULER] Schedule '{sched.get('name')}' is due to run")

                    # Query sensor (only once when schedule is due)
                    env = None
                    hum = None
                    temp = None
                    
                    try:
                        env = _sensor.get_environment(use_cache=True)
                        if env:
                            hum = env.get("hum")
                            temp = env.get("temp")
                            logger.info(f"[SCHEDULER] Sensor reading: temp={temp}°C, hum={hum}%")
                    except SensorError as e:
                        logger.warning(f"[SCHEDULER] Sensor error, proceeding without humidity check: {e}")
                    except Exception as e:
                        logger.exception(f"[SCHEDULER] Unexpected sensor error: {e}")

                    # Check humidity threshold
                    if hum is not None and hum > HUMIDITY_SKIP_THRESHOLD:
                        logger.info(
                            f"[SCHEDULER] Skipping '{sched.get('name')}' due to high humidity: "
                            f"{hum:.1f}% > {HUMIDITY_SKIP_THRESHOLD}%"
                        )
                        log_skipped_run(sched, now, hum, temp)
                        
                        # Save updated schedule (with last_skipped)
                        try:
                            save_schedules(scheds)
                        except Exception as e:
                            logger.error(f"[SCHEDULER] Error saving schedule after skip: {e}")
                        
                        continue

                    # Normal execution: mark as run and start sequence
                    logger.info(f"[SCHEDULER] Executing schedule: {sched.get('name')}")
                    mark_last_run(sched, now)
                    
                    # Save immediately to prevent duplicate runs
                    try:
                        save_schedules(scheds)
                    except Exception as e:
                        logger.error(f"[SCHEDULER] Error saving schedule after marking run: {e}")

                    # Start sequence in a new thread (non-blocking)
                    # Note: Only one sequence runs at a time due to exclusive_on
                    Thread(target=run_sequence, args=(sched,), daemon=True).start()

                except Exception as e:
                    logger.exception(f"[SCHEDULER] Error processing schedule '{sched.get('name')}': {e}")
                    # Continue to next schedule

            # Sleep until next check
            time.sleep(CHECK_INTERVAL_SEC)

        except Exception as e:
            # Catch-all for any unexpected errors in main loop
            logger.exception(f"[SCHEDULER] Critical error in scheduler loop: {e}")
            
            # Try to turn off all zones as safety measure
            try:
                all_off()
                set_current_run(active=False, name=None, step="error", ends_at=None)
            except Exception as off_error:
                logger.error(f"[SCHEDULER] Error in emergency shutdown: {off_error}")
            
            # Sleep before retrying
            time.sleep(CHECK_INTERVAL_SEC)


def start_scheduler():
    """Start the background scheduler thread."""
    logger.info("[SCHEDULER] Starting scheduler thread")
    thread = Thread(target=scheduler_loop, daemon=True, name="Scheduler")
    thread.start()
    logger.info("[SCHEDULER] Scheduler thread started")
