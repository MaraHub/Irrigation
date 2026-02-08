"""
Shared application state for tracking current operations.
Thread-safe state management for concurrent access.
"""
from threading import Lock, Event
from typing import Optional, Dict, Any
from datetime import datetime


# ============================================================================
# Thread synchronization primitives
# ============================================================================

state_lock = Lock()
run_cancel = Event()


# ============================================================================
# Current run state
# ============================================================================

current_run: Dict[str, Any] = {
    "active": False,
    "name": None,
    "step": None,
    "ends_at": None,
    "started_at": None,
    "schedule_id": None,
}


# ============================================================================
# Environment state (cached sensor readings)
# ============================================================================

env_state: Dict[str, Optional[float]] = {
    "temp": None,
    "hum": None,
    "last_update": None,
}


# ============================================================================
# Helper functions
# ============================================================================

def set_current_run(active: bool, name: Optional[str] = None, 
                    step: Optional[str] = None, ends_at: Optional[datetime] = None,
                    schedule_id: Optional[str] = None):
    """Update current run state in a thread-safe manner."""
    with state_lock:
        current_run["active"] = active
        current_run["name"] = name
        current_run["step"] = step
        current_run["ends_at"] = ends_at
        current_run["started_at"] = datetime.now() if active else None
        current_run["schedule_id"] = schedule_id


def get_current_run() -> Dict[str, Any]:
    """Get a snapshot of current run state."""
    with state_lock:
        return current_run.copy()


def update_env_state(temp: Optional[float], hum: Optional[float]):
    """Update environment state in a thread-safe manner."""
    with state_lock:
        env_state["temp"] = temp
        env_state["hum"] = hum
        env_state["last_update"] = datetime.now()


def get_env_state() -> Dict[str, Optional[float]]:
    """Get a snapshot of environment state."""
    with state_lock:
        return env_state.copy()


def clear_run_cancel():
    """Clear the cancel event flag."""
    run_cancel.clear()


def request_run_cancel():
    """Request cancellation of current run."""
    run_cancel.set()


def is_cancel_requested() -> bool:
    """Check if cancellation has been requested."""
    return run_cancel.is_set()
