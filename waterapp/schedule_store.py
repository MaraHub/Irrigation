"""
Schedule storage and management functions.
Handles JSON persistence with atomic writes and proper error handling.
"""
import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from .config import SCHED_FILE, SKIP_LOG_FILE, HARDWARE_ERROR_LOG

logger = logging.getLogger(__name__)


# ============================================================================
# Schedule File Operations
# ============================================================================

def load_schedules() -> List[Dict[str, Any]]:
    """
    Load schedules from JSON file.
    
    Returns empty list if file doesn't exist or is corrupted.
    """
    if not os.path.exists(SCHED_FILE):
        logger.info(f"[SCHEDULES] No schedule file found at {SCHED_FILE}")
        return []
    
    try:
        with open(SCHED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            logger.warning(f"[SCHEDULES] Invalid data type in {SCHED_FILE}, expected list")
            return []
        
        logger.info(f"[SCHEDULES] Loaded {len(data)} schedules")
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"[SCHEDULES] JSON decode error in {SCHED_FILE}: {e}")
        # Backup corrupted file
        backup_path = f"{SCHED_FILE}.corrupted.{int(datetime.now().timestamp())}"
        try:
            os.rename(SCHED_FILE, backup_path)
            logger.info(f"[SCHEDULES] Backed up corrupted file to {backup_path}")
        except Exception as be:
            logger.error(f"[SCHEDULES] Could not backup corrupted file: {be}")
        return []
        
    except Exception as e:
        logger.error(f"[SCHEDULES] Error loading schedules: {e}", exc_info=True)
        return []


def save_schedules(schedules: List[Dict[str, Any]]) -> bool:
    """
    Save schedules to JSON file atomically.
    
    Uses temporary file + rename for atomic write.
    Returns True on success, False on failure.
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(SCHED_FILE), exist_ok=True)
        
        # Write to temporary file first
        tmp_file = f"{SCHED_FILE}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(schedules, f, indent=2, ensure_ascii=False)
        
        # Atomic replace
        os.replace(tmp_file, SCHED_FILE)
        
        logger.info(f"[SCHEDULES] Saved {len(schedules)} schedules to {SCHED_FILE}")
        return True
        
    except Exception as e:
        logger.error(f"[SCHEDULES] Error saving schedules: {e}", exc_info=True)
        # Clean up temp file if it exists
        try:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
        except:
            pass
        return False


# ============================================================================
# Schedule Status Updates
# ============================================================================

def mark_last_run(schedule: Dict[str, Any], when_dt: datetime):
    """
    Mark when a schedule was last executed.
    
    Args:
        schedule: Schedule dictionary to update
        when_dt: Datetime of execution
    """
    schedule["last_run"] = when_dt.strftime("%Y-%m-%d %H:%M")
    logger.debug(f"[SCHEDULES] Marked last_run for '{schedule.get('name')}': {schedule['last_run']}")


# ============================================================================
# Schedule Matching Logic
# ============================================================================

def should_run_today(days_list: List[str], dt: datetime) -> bool:
    """
    Check if a schedule should run on the given date.
    
    Args:
        days_list: List of day abbreviations (e.g., ['Mon', 'Wed', 'Fri'])
        dt: Datetime to check
    
    Returns:
        True if the schedule should run on this day
    """
    day_map = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    current_day = day_map[dt.weekday()]
    return current_day in days_list


def time_matches(start_time_str: str, dt: datetime) -> bool:
    """
    Check if the current time matches the schedule start time.
    
    Args:
        start_time_str: Time in "HH:MM" format
        dt: Datetime to check
    
    Returns:
        True if hour and minute match
    """
    try:
        hour, minute = [int(x) for x in start_time_str.split(":")]
        return dt.hour == hour and dt.minute == minute
    except (ValueError, AttributeError) as e:
        logger.error(f"[SCHEDULES] Invalid time format '{start_time_str}': {e}")
        return False


def already_ran_this_minute(schedule: Dict[str, Any], dt: datetime) -> bool:
    """
    Check if schedule already ran in this specific minute.
    
    Prevents duplicate runs within the same minute.
    
    Args:
        schedule: Schedule dictionary with 'last_run' field
        dt: Current datetime
    
    Returns:
        True if already ran in this minute
    """
    last_run_str = schedule.get("last_run")
    if not last_run_str:
        return False
    
    try:
        last_run_dt = datetime.strptime(last_run_str, "%Y-%m-%d %H:%M")
        return (
            last_run_dt.year == dt.year and
            last_run_dt.month == dt.month and
            last_run_dt.day == dt.day and
            last_run_dt.hour == dt.hour and
            last_run_dt.minute == dt.minute
        )
    except (ValueError, AttributeError) as e:
        logger.error(f"[SCHEDULES] Error parsing last_run '{last_run_str}': {e}")
        return False


# ============================================================================
# Skip Logging (for humidity-based skips)
# ============================================================================

def log_skipped_run(schedule: Dict[str, Any], when_dt: datetime, 
                   humidity: float, temp: Optional[float]):
    """
    Log a skipped irrigation run to file and update schedule.
    
    This tracks when runs were skipped due to high humidity.
    
    Args:
        schedule: The schedule that was skipped
        when_dt: When the skip occurred
        humidity: Humidity reading that triggered skip
        temp: Temperature reading (may be None)
    """
    record = {
        "time": when_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "schedule_id": schedule.get("id"),
        "schedule_name": schedule.get("name"),
        "humidity": float(humidity),
        "temp": float(temp) if temp is not None else None,
    }
    
    try:
        # Load existing log
        log_entries = []
        if os.path.exists(SKIP_LOG_FILE):
            try:
                with open(SKIP_LOG_FILE, "r", encoding="utf-8") as f:
                    log_entries = json.load(f)
                if not isinstance(log_entries, list):
                    log_entries = []
            except json.JSONDecodeError:
                logger.warning(f"[SKIP_LOG] Corrupted log file, starting fresh")
                log_entries = []
        
        # Append new record
        log_entries.append(record)
        
        # Keep only last 100 entries to prevent file from growing indefinitely
        if len(log_entries) > 100:
            log_entries = log_entries[-100:]
        
        # Write atomically
        os.makedirs(os.path.dirname(SKIP_LOG_FILE), exist_ok=True)
        tmp_file = f"{SKIP_LOG_FILE}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(log_entries, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, SKIP_LOG_FILE)
        
        # Update schedule with compact summary
        schedule["last_skipped"] = {
            "time": record["time"],
            "humidity": record["humidity"],
            "temp": record["temp"],
        }
        
        logger.info(
            f"[SKIP_LOG] Logged skip for '{schedule.get('name')}' "
            f"(humidity: {humidity:.1f}%)"
        )
        
    except Exception as e:
        logger.error(f"[SKIP_LOG] Error logging skipped run: {e}", exc_info=True)


# ============================================================================
# Hardware Error Logging
# ============================================================================

def log_hardware_error(device_id: str, error_msg: str, error_type: str = "unknown"):
    """
    Log hardware errors to a separate file for monitoring.
    
    Args:
        device_id: Device identifier (e.g., 'R1', 'S1')
        error_msg: Error message
        error_type: Type of error (e.g., 'timeout', 'connection', 'gpio')
    """
    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "device_id": device_id,
        "error_type": error_type,
        "error_msg": error_msg,
    }
    
    try:
        # Load existing log
        log_entries = []
        if os.path.exists(HARDWARE_ERROR_LOG):
            try:
                with open(HARDWARE_ERROR_LOG, "r", encoding="utf-8") as f:
                    log_entries = json.load(f)
                if not isinstance(log_entries, list):
                    log_entries = []
            except json.JSONDecodeError:
                logger.warning(f"[HW_ERROR_LOG] Corrupted log file, starting fresh")
                log_entries = []
        
        # Append new record
        log_entries.append(record)
        
        # Keep only last 200 entries
        if len(log_entries) > 200:
            log_entries = log_entries[-200:]
        
        # Write atomically
        os.makedirs(os.path.dirname(HARDWARE_ERROR_LOG), exist_ok=True)
        tmp_file = f"{HARDWARE_ERROR_LOG}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(log_entries, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, HARDWARE_ERROR_LOG)
        
        logger.debug(f"[HW_ERROR_LOG] Logged error for device {device_id}")
        
    except Exception as e:
        logger.error(f"[HW_ERROR_LOG] Error logging hardware error: {e}", exc_info=True)


def get_recent_hardware_errors(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get recent hardware error log entries.
    
    Args:
        limit: Maximum number of entries to return
    
    Returns:
        List of error records, most recent first
    """
    try:
        if not os.path.exists(HARDWARE_ERROR_LOG):
            return []
        
        with open(HARDWARE_ERROR_LOG, "r", encoding="utf-8") as f:
            log_entries = json.load(f)
        
        if not isinstance(log_entries, list):
            return []
        
        # Return most recent entries first
        return log_entries[-limit:][::-1]
        
    except Exception as e:
        logger.error(f"[HW_ERROR_LOG] Error reading hardware errors: {e}")
        return []
