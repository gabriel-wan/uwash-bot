import sqlite3
import datetime
import os
from config import config

DATABASE_PATH = None

def get_db_path():
    """Get database file path."""
    global DATABASE_PATH
    if DATABASE_PATH is None:
        base_path = config.get("BASE_PATH", "./data")
        DATABASE_PATH = os.path.join(base_path, "uwash.db")

        # Ensure directory exists
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    return DATABASE_PATH

def init_database():
    """Initialize database tables."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Timers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS timers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            house TEXT NOT NULL,
            machine_name TEXT NOT NULL,
            curr_user TEXT NOT NULL,
            start_time INTEGER NOT NULL,
            end_time INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(house, machine_name)
        )
    ''')

    # House preferences table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS house_preferences (
            user_id TEXT PRIMARY KEY,
            house TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Alarms table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alarms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            curr_user TEXT NOT NULL,
            machine_house_name TEXT NOT NULL,
            end_timestamp INTEGER NOT NULL,
            chat_id TEXT NOT NULL,
            thread_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Queue table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            house TEXT NOT NULL,
            machine_type TEXT NOT NULL,
            telegram_id TEXT NOT NULL,
            telegram_username TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'waiting',
            notified_at TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print(f"[Database] Initialized at {get_db_path()}")

def set_laundry_timer(house: str, machine_name: str, curr_user: str, end_time: datetime.datetime,
                     chat_id: int = None, thread_id: int = None, start_time: datetime.datetime = None):
    """Set a laundry timer."""
    if start_time is None:
        start_time = datetime.datetime.now()

    start_timestamp = int(start_time.timestamp())
    end_timestamp = int(end_time.timestamp())

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Insert or replace timer
    cursor.execute('''
        INSERT OR REPLACE INTO timers (house, machine_name, curr_user, start_time, end_time)
        VALUES (?, ?, ?, ?, ?)
    ''', (house, machine_name, curr_user, start_timestamp, end_timestamp))

    # Add alarm if chat_id provided
    if chat_id is not None:
        cursor.execute('''
            INSERT INTO alarms (curr_user, machine_house_name, end_timestamp, chat_id, thread_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (curr_user, f"{house} {machine_name}", end_timestamp, str(chat_id), str(thread_id) if thread_id else None))

    conn.commit()
    conn.close()

def get_laundry_timer(house: str, machine_name: str) -> tuple[str, datetime.datetime, datetime.datetime]:
    """Get laundry timer for a machine."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute('''
        SELECT curr_user, start_time, end_time
        FROM timers
        WHERE house = ? AND machine_name = ?
    ''', (house, machine_name))

    result = cursor.fetchone()
    conn.close()

    if result:
        curr_user, start_timestamp, end_timestamp = result
        start_time = datetime.datetime.fromtimestamp(start_timestamp) if start_timestamp else None
        end_time = datetime.datetime.fromtimestamp(end_timestamp)
        return (curr_user, end_time, start_time)

    return ("", None, None)

def set_laundry_timer_sensor(house: str, machine_name: str, end_time: datetime.datetime):
    """Set timer from hardware sensor."""
    set_laundry_timer(house, machine_name, "sensor", end_time)

def clear_laundry_timer(house: str, machine_name: str):
    """Clear a laundry timer."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute('DELETE FROM timers WHERE house = ? AND machine_name = ?', (house, machine_name))

    conn.commit()
    conn.close()

def write_house(user_id: int, house: str):
    """Store user's house preference."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO house_preferences (user_id, house)
        VALUES (?, ?)
    ''', (str(user_id), house))

    conn.commit()
    conn.close()

def get_house(user_id: int) -> str:
    """Get user's house preference."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute('SELECT house FROM house_preferences WHERE user_id = ?', (str(user_id),))
    result = cursor.fetchone()
    conn.close()

    return result[0] if result else None

def check_alarms() -> list[tuple[str, str, str, str]]:
    """Check for due alarms and return them."""
    now_timestamp = int(datetime.datetime.now().timestamp())

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Get due alarms
    cursor.execute('''
        SELECT curr_user, chat_id, thread_id, machine_house_name
        FROM alarms
        WHERE end_timestamp <= ?
    ''', (now_timestamp,))

    due_alarms = cursor.fetchall()

    # Remove processed alarms
    if due_alarms:
        cursor.execute('DELETE FROM alarms WHERE end_timestamp <= ?', (now_timestamp,))

    conn.commit()
    conn.close()

    return due_alarms

def read_timers():
    """Initialize database - compatibility function."""
    init_database()

def read_house():
    """Initialize database - compatibility function."""
    init_database()

# Initialize on import
if __name__ != "__main__":
    init_database()


# ============ Queue Functions ============

def join_queue(house: str, machine_type: str, telegram_id: str, telegram_username: str = None) -> dict:
    """Add user to queue. Returns position and queue info."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Check if user already in queue for this house + machine_type
    cursor.execute('''
        SELECT id, status FROM queue
        WHERE house = ? AND machine_type = ? AND telegram_id = ? AND status IN ('waiting', 'notified')
    ''', (house, machine_type, telegram_id))
    existing = cursor.fetchone()

    if existing:
        # Already in queue, return current position
        position = get_queue_position(house, machine_type, telegram_id)
        conn.close()
        return {"status": "already_queued", "position": position}

    # Add to queue
    cursor.execute('''
        INSERT INTO queue (house, machine_type, telegram_id, telegram_username, status)
        VALUES (?, ?, ?, ?, 'waiting')
    ''', (house, machine_type, telegram_id, telegram_username))

    conn.commit()
    conn.close()

    # Get position
    position = get_queue_position(house, machine_type, telegram_id)
    return {"status": "joined", "position": position}


def get_queue_position(house: str, machine_type: str, telegram_id: str) -> int:
    """Get user's position in queue (1-indexed). Returns 0 if not in queue."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute('''
        SELECT telegram_id FROM queue
        WHERE house = ? AND machine_type = ? AND status IN ('waiting', 'notified')
        ORDER BY joined_at ASC
    ''', (house, machine_type))

    queue_list = cursor.fetchall()
    conn.close()

    for i, (tid,) in enumerate(queue_list, 1):
        if tid == telegram_id:
            return i
    return 0


def get_queue(house: str) -> dict:
    """Get all queue entries for a house, grouped by machine type."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Get washer queue
    cursor.execute('''
        SELECT id, telegram_id, telegram_username, joined_at, status
        FROM queue
        WHERE house = ? AND machine_type = 'washer' AND status IN ('waiting', 'notified')
        ORDER BY joined_at ASC
    ''', (house,))
    washer_rows = cursor.fetchall()

    # Get dryer queue
    cursor.execute('''
        SELECT id, telegram_id, telegram_username, joined_at, status
        FROM queue
        WHERE house = ? AND machine_type = 'dryer' AND status IN ('waiting', 'notified')
        ORDER BY joined_at ASC
    ''', (house,))
    dryer_rows = cursor.fetchall()

    conn.close()

    # Build response with estimated wait times
    # Assume 45 min avg for washers, 60 min for dryers
    WASHER_AVG_MINS = 45
    DRYER_AVG_MINS = 60

    def build_queue_list(rows, avg_mins):
        result = []
        for i, (qid, tid, username, joined_at, status) in enumerate(rows, 1):
            result.append({
                "id": qid,
                "position": i,
                "telegram_id": tid,
                "username": username or "Anonymous",
                "joined_at": joined_at,
                "status": status,
                "estimated_wait_mins": i * avg_mins
            })
        return result

    return {
        "washer": {
            "queue": build_queue_list(washer_rows, WASHER_AVG_MINS),
            "count": len(washer_rows)
        },
        "dryer": {
            "queue": build_queue_list(dryer_rows, DRYER_AVG_MINS),
            "count": len(dryer_rows)
        }
    }


def leave_queue(house: str, telegram_id: str, machine_type: str = None) -> bool:
    """Remove user from queue. Returns True if removed, False if not found."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    if machine_type:
        cursor.execute('''
            DELETE FROM queue
            WHERE house = ? AND telegram_id = ? AND machine_type = ? AND status IN ('waiting', 'notified')
        ''', (house, telegram_id, machine_type))
    else:
        # Remove from all queues for this house
        cursor.execute('''
            DELETE FROM queue
            WHERE house = ? AND telegram_id = ? AND status IN ('waiting', 'notified')
        ''', (house, telegram_id))

    removed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return removed


def get_next_in_queue(house: str, machine_type: str) -> tuple:
    """Get the next person in queue to notify. Returns (id, telegram_id, username) or None."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Get first waiting person (not already notified)
    cursor.execute('''
        SELECT id, telegram_id, telegram_username FROM queue
        WHERE house = ? AND machine_type = ? AND status = 'waiting'
        ORDER BY joined_at ASC
        LIMIT 1
    ''', (house, machine_type))

    result = cursor.fetchone()
    conn.close()

    return result  # (id, telegram_id, username) or None


def mark_queue_notified(queue_id: int):
    """Mark a queue entry as notified."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE queue SET status = 'notified', notified_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (queue_id,))

    conn.commit()
    conn.close()


def remove_from_queue(queue_id: int):
    """Remove a specific queue entry (e.g., after user claims machine)."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute('DELETE FROM queue WHERE id = ?', (queue_id,))

    conn.commit()
    conn.close()


def expire_old_notifications(timeout_mins: int = 10):
    """Expire notifications older than timeout and move to next person."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cutoff = datetime.datetime.now() - datetime.timedelta(minutes=timeout_mins)

    cursor.execute('''
        UPDATE queue SET status = 'expired'
        WHERE status = 'notified' AND notified_at < ?
    ''', (cutoff.isoformat(),))

    conn.commit()
    conn.close()