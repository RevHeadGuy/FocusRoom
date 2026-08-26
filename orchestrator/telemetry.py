import contextvars
import uuid
from datetime import datetime


_current_execution_id = contextvars.ContextVar(
    "current_execution_id",
    default=None
)


def start_execution():
    execution_id = str(uuid.uuid4())
    _current_execution_id.set(execution_id)
    return execution_id


def get_execution_id():
    return _current_execution_id.get()


def set_execution_id(execution_id):
    _current_execution_id.set(execution_id)


def record_event(db, event_type, name, details=None):
    execution_id = get_execution_id()

    if not execution_id:
        return

    db.save_execution_event({
        "execution_id": execution_id,
        "event_type": event_type,
        "name": name,
        "details": details or {},
        "created_at": datetime.now().isoformat()
    })


def finish_execution():
    _current_execution_id.set(None)
