import datetime
import json
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import db_storage as storage
import uwashbotbackend.constants as constants
from config import config

app = Flask(__name__)
CORS(app)

MACHINES_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "machines.json")

@app.route("/api/collect", methods=["POST"])
def mark_collected():
    """Endpoint to mark laundry as collected, clearing timer and setting machine to available."""
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400

    house = data.get("house")
    machine_name = data.get("machine_name")
    telegram_id = data.get("telegram_id")  # Optional, for future user validation

    # Validate house and machine_name
    normalized_house = _normalize_house(house) if house else None
    if not normalized_house:
        return jsonify({"status": "error", "message": f"Invalid house. Valid: {list(constants.HOUSES.keys())}"}), 400
    if machine_name not in constants.MACHINE_NAMES:
        return jsonify({"status": "error", "message": f"Invalid machine_name. Valid: {constants.MACHINE_NAMES}"}), 400

    # Check if machine is in idle state (optional: can allow any state)
    now = datetime.datetime.now()
    curr_user, end_time, _ = storage.get_laundry_timer(normalized_house, machine_name)
    if not curr_user or not end_time or end_time > now:
        return jsonify({"status": "error", "message": f"{machine_name} is not in idle state"}), 409

    # Clear the timer and set status to available
    storage.clear_laundry_timer(normalized_house, machine_name)
    _sync_to_machines_json(normalized_house, machine_name, "available")

    # Notify next person in queue
    machine_type = _get_machine_kind(machine_name)
    notified_user = _notify_next_in_queue(normalized_house, machine_type)

    # Return updated status
    return jsonify({
        "status": "success",
        "message": f"{machine_name} is now available",
        "house": normalized_house,
        "machine": machine_name,
        "new_status": "available",
        "notified_user": notified_user
    }), 200

@app.after_request
def add_cors_headers(response):
    """Add CORS headers to allow dashboard requests."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
    return response


def _check_api_key() -> bool:
    api_key = config.get("SENSOR_API_KEY")
    if api_key and request.headers.get("X-API-Key") != api_key:
        return False
    return True


def _normalize_house(house: str) -> str | None:
    """Normalize house name to match constants (case-insensitive)."""
    if not house:
        return None

    alias_house = constants.HOUSE_ALIASES.get(house.lower())
    if alias_house:
        return alias_house

    house_lower = house.lower()
    for h in constants.HOUSES.keys():
        if h.lower() == house_lower:
            return h
    return None


def _normalize_college(college: str | None) -> str | None:
    if not college:
        return None
    college_lower = college.lower()
    if college_lower in constants.COLLEGE_HOUSES:
        return college_lower
    return None


def _house_college(house: str) -> str:
    return constants.HOUSE_TO_COLLEGE.get(house, "capt")


def _get_machine_kind(machine_name: str) -> str:
    """Determine if machine is washer or dryer based on name."""
    return "washer" if "washer" in machine_name.lower() else "dryer"


def _build_machine_status(house_id: str, machine_name: str, now: datetime.datetime) -> dict:
    """Build a single machine's status in dashboard format."""
    curr_user, end_time, start_time = storage.get_laundry_timer(house_id, machine_name)
    kind = _get_machine_kind(machine_name)

    # Get queue length for this machine type
    queue_data = storage.get_queue(house_id)
    queue_length = queue_data[kind]["count"] if kind in queue_data else 0

    if end_time and end_time > now:
        return {
            "status": "in_use",
            "kind": kind,
            "currUser": None if curr_user == "sensor" else curr_user,
            "startTimeMs": int(start_time.timestamp() * 1000) if start_time else None,
            "endTime": int(end_time.timestamp() * 1000),
            "hardwareDetected": curr_user == "sensor",
            "queueLength": queue_length,
            "cycleEndedAtMs": None,
        }
    elif end_time and end_time <= now and curr_user:
        return {
            "status": "idle",
            "kind": kind,
            "currUser": None if curr_user == "sensor" else curr_user,
            "startTimeMs": None,
            "endTime": None,
            "hardwareDetected": curr_user == "sensor",
            "queueLength": queue_length,
            "cycleEndedAtMs": int(end_time.timestamp() * 1000),
        }
    else:
        return {
            "status": "available",
            "kind": kind,
            "currUser": None,
            "startTimeMs": None,
            "endTime": None,
            "hardwareDetected": False,
            "queueLength": queue_length,
            "cycleEndedAtMs": None,
        }


def _sync_to_machines_json(house: str, machine_name: str, status: str):
    """Sync sensor update to machines.json for dashboard consumption."""
    try:
        # Load or initialize machines.json
        if os.path.exists(MACHINES_JSON_PATH):
            with open(MACHINES_JSON_PATH, 'r') as f:
                state = json.load(f)
        else:
            state = {"college": "capt", "house": house, "lastUpdatedMs": 0, "machines": {}}

        # Ensure machines dict exists
        if "machines" not in state:
            state["machines"] = {}

        # Update the machine status
        if machine_name in state["machines"]:
            state["machines"][machine_name]["status"] = status
            state["machines"][machine_name]["hardwareDetected"] = True
            state["lastUpdatedMs"] = int(datetime.datetime.now().timestamp() * 1000)

        # Write back
        os.makedirs(os.path.dirname(MACHINES_JSON_PATH) or ".", exist_ok=True)
        with open(MACHINES_JSON_PATH, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[WARNING] Failed to sync to machines.json: {e}")


@app.route("/machine/update", methods=["POST"])
def update_machine():
    if not _check_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    house = data.get("house")
    machine_name = data.get("machine_name")
    status = data.get("status")

    if house not in constants.HOUSES:
        return jsonify({"error": f"Invalid house. Valid: {list(constants.HOUSES.keys())}"}), 400
    if machine_name not in constants.MACHINE_NAMES:
        return jsonify({"error": f"Invalid machine_name. Valid: {constants.MACHINE_NAMES}"}), 400
    if status not in ("in_use", "available"):
        return jsonify({"error": "status must be 'in_use' or 'available'"}), 400

    if status == "in_use":
        # Sensor doesn't know cycle length, so set a 2-hour ceiling.
        # The "available" POST from the sensor will clear this early when vibration stops.
        end_time = datetime.datetime.now() + datetime.timedelta(hours=2)
        storage.set_laundry_timer_sensor(house, machine_name, end_time)
        notified_user = None
    else:
        storage.clear_laundry_timer(house, machine_name)
        # Notify next person in queue when machine becomes available
        machine_type = _get_machine_kind(machine_name)
        notified_user = _notify_next_in_queue(house, machine_type)

    # Sync to machines.json for dashboard
    _sync_to_machines_json(house, machine_name, status)

    return jsonify({
        "status": "ok",
        "house": house,
        "machine": machine_name,
        "new_status": status,
        "notified_user": notified_user
    })


@app.route("/status", methods=["GET"])
def get_status_legacy():
    """Legacy endpoint - returns old format for backwards compatibility."""
    now = datetime.datetime.now()
    machines = {}
    for house_id in constants.HOUSES.keys():
        machines[house_id] = {}
        for machine_name in constants.MACHINE_NAMES:
            curr_user, end_time, _ = storage.get_laundry_timer(house_id, machine_name)
            if end_time and end_time > now:
                machines[house_id][machine_name] = {
                    "status": "in_use",
                    "curr_user": curr_user,
                    "end_time": int(end_time.timestamp()),
                    "minutes_remaining": int((end_time - now).total_seconds() / 60),
                }
            else:
                machines[house_id][machine_name] = {
                    "status": "available",
                    "last_user": curr_user if curr_user else None,
                }
    return jsonify(machines)


@app.route("/api/status", methods=["GET"])
def get_status():
    """Get status for all houses in dashboard format."""
    now = datetime.datetime.now()
    result = {}

    for house_id in constants.HOUSES.keys():
        machines = {}
        for machine_name in constants.MACHINE_NAMES:
            machines[machine_name] = _build_machine_status(house_id, machine_name, now)

        result[house_id] = {
            "college": _house_college(house_id),
            "house": house_id,
            "lastUpdatedMs": int(now.timestamp() * 1000),
            "machines": machines,
        }

    return jsonify(result)


@app.route("/api/<house>/status", methods=["GET"])
@app.route("/api/<college>/<house>/status", methods=["GET"])
def get_house_status(house: str, college: str | None = None):
    """Get status for a specific house in dashboard format."""
    normalized_house = _normalize_house(house)
    if not normalized_house:
        return jsonify({"error": f"Invalid house. Valid: {list(constants.HOUSES.keys())}"}), 400
    normalized_college = _normalize_college(college)
    if normalized_college:
        valid_houses = constants.COLLEGE_HOUSES.get(normalized_college, [])
        if normalized_house not in valid_houses:
            return jsonify({
                "error": f"House '{normalized_house}' does not belong to college '{normalized_college}'"
            }), 400

    now = datetime.datetime.now()
    machines = {}
    for machine_name in constants.MACHINE_NAMES:
        machines[machine_name] = _build_machine_status(normalized_house, machine_name, now)

    return jsonify({
        "college": normalized_college or _house_college(normalized_house),
        "house": normalized_house,
        "lastUpdatedMs": int(now.timestamp() * 1000),
        "machines": machines,
    })


@app.route("/api/start-cycle", methods=["POST"])
def start_cycle():
    """Start a laundry cycle from the dashboard."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    house = data.get("house")
    machine_name = data.get("machine_name")
    username = data.get("username")
    duration_mins = data.get("duration_mins", 30)

    normalized_house = _normalize_house(house) if house else None
    if not normalized_house:
        return jsonify({"error": f"Invalid house. Valid: {list(constants.HOUSES.keys())}"}), 400
    if machine_name not in constants.MACHINE_NAMES:
        return jsonify({"error": f"Invalid machine_name. Valid: {constants.MACHINE_NAMES}"}), 400
    if not username:
        return jsonify({"error": "username is required"}), 400

    now = datetime.datetime.now()
    curr_user, end_time, _ = storage.get_laundry_timer(normalized_house, machine_name)
    if end_time and end_time > now:
        return jsonify({"error": f"{machine_name} is currently in use"}), 409

    end_time = now + datetime.timedelta(minutes=duration_mins)
    storage.set_laundry_timer(normalized_house, machine_name, username, end_time, start_time=now)

    return jsonify({
        "status": "ok",
        "house": normalized_house,
        "machine": machine_name,
        "username": username,
        "endTimeMs": int(end_time.timestamp() * 1000),
    })


# ============ Queue Endpoints ============

def _notify_next_in_queue(house: str, machine_type: str) -> str | None:
    """Notify next person in queue when a machine becomes available.
    Returns the username if someone was notified, None otherwise."""
    next_user = storage.get_next_in_queue(house, machine_type)
    if not next_user:
        return None

    queue_id, telegram_id, username = next_user
    storage.mark_queue_notified(queue_id)

    # TODO: Send actual Telegram message via bot
    # For now, just mark as notified and return username
    print(f"[Queue] Notified {username} ({telegram_id}) - {machine_type} available in {house}")

    return username


def _build_queue_response(normalized_house: str, college: str | None = None) -> dict:
    queue_data = storage.get_queue(normalized_house)
    washer_queue = queue_data["washer"]["queue"]
    dryer_queue = queue_data["dryer"]["queue"]
    now_ms = int(datetime.datetime.now().timestamp() * 1000)

    by_machine = {}
    for machine_name in constants.MACHINE_NAMES:
        kind = _get_machine_kind(machine_name)
        rows = washer_queue if kind == "washer" else dryer_queue
        by_machine[machine_name] = {
            "queueLength": len(rows),
            "estWaitMins": len(rows) * (45 if kind == "washer" else 60),
            "members": [
                {"username": row.get("username", "Anonymous"), "position": row.get("position", i + 1)}
                for i, row in enumerate(rows)
            ],
        }

    return {
        # New dashboard shape
        "college": college or _house_college(normalized_house),
        "house": normalized_house,
        "lastUpdatedMs": now_ms,
        "byMachine": by_machine,
        # Backward-compatible shape
        "washer": queue_data["washer"],
        "dryer": queue_data["dryer"],
    }


@app.route("/api/queue/join", methods=["POST"])
@app.route("/api/join-queue", methods=["POST"])
@app.route("/api/<house>/queue/join", methods=["POST"])
@app.route("/api/<college>/<house>/queue/join", methods=["POST"])
def join_queue(house: str | None = None, college: str | None = None):
    """Join the queue for a machine type."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    house = data.get("house") or house
    machine_type = data.get("machine_type")  # 'washer' or 'dryer'
    machine_name = data.get("machine_name") or data.get("machineId")
    if not machine_type and machine_name:
        machine_type = _get_machine_kind(machine_name)

    username = (data.get("username") or "").strip()
    telegram_id = (
        data.get("telegram_id")
        or data.get("userId")
        or (username if username else None)
    )
    # Validate inputs
    normalized_house = _normalize_house(house) if house else None
    if not normalized_house:
        return jsonify({"error": f"Invalid house. Valid: {list(constants.HOUSES.keys())}"}), 400
    normalized_college = _normalize_college(data.get("college") or college)
    if normalized_college:
        valid_houses = constants.COLLEGE_HOUSES.get(normalized_college, [])
        if normalized_house not in valid_houses:
            return jsonify({
                "error": f"House '{normalized_house}' does not belong to college '{normalized_college}'"
            }), 400
    if machine_type not in ("washer", "dryer"):
        return jsonify({"error": "machine_type must be 'washer' or 'dryer'"}), 400
    if not telegram_id:
        return jsonify({"error": "telegram_id is required"}), 400

    # Join the queue
    result = storage.join_queue(normalized_house, machine_type, telegram_id, username)

    # Calculate estimated wait time
    WAIT_TIMES = {"washer": 45, "dryer": 60}
    estimated_wait_mins = result["position"] * WAIT_TIMES[machine_type]

    return jsonify({
        "status": result["status"],
        "house": normalized_house,
        "machine_type": machine_type,
        "position": result["position"],
        "estimated_wait_mins": estimated_wait_mins
    })


@app.route("/api/queue", methods=["GET"])
@app.route("/api/<house>/queue", methods=["GET"])
@app.route("/api/<college>/<house>/queue", methods=["GET"])
def get_queue(house: str | None = None, college: str | None = None):
    """Get queue status for a house."""
    house = request.args.get("house") or house
    college = request.args.get("college") or college

    normalized_house = _normalize_house(house) if house else None
    if not normalized_house:
        return jsonify({"error": f"Invalid house. Valid: {list(constants.HOUSES.keys())}"}), 400
    normalized_college = _normalize_college(college)
    if normalized_college:
        valid_houses = constants.COLLEGE_HOUSES.get(normalized_college, [])
        if normalized_house not in valid_houses:
            return jsonify({
                "error": f"House '{normalized_house}' does not belong to college '{normalized_college}'"
            }), 400

    return jsonify(_build_queue_response(normalized_house, normalized_college))


@app.route("/api/queue/leave", methods=["DELETE", "POST"])
def leave_queue():
    """Leave the queue."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    house = data.get("house")
    telegram_id = data.get("telegram_id")
    machine_type = data.get("machine_type")  # optional, if not provided leaves all queues

    normalized_house = _normalize_house(house) if house else None
    if not normalized_house:
        return jsonify({"error": f"Invalid house. Valid: {list(constants.HOUSES.keys())}"}), 400
    if not telegram_id:
        return jsonify({"error": "telegram_id is required"}), 400

    removed = storage.leave_queue(normalized_house, telegram_id, machine_type)

    if removed:
        return jsonify({"status": "success", "message": "Removed from queue"})
    else:
        return jsonify({"status": "not_found", "message": "User not in queue"}), 404


@app.route("/api/queue/position", methods=["GET"])
def get_queue_position():
    """Get user's current position in queue."""
    house = request.args.get("house")
    telegram_id = request.args.get("telegram_id")
    machine_type = request.args.get("machine_type")

    normalized_house = _normalize_house(house) if house else None
    if not normalized_house:
        return jsonify({"error": f"Invalid house. Valid: {list(constants.HOUSES.keys())}"}), 400
    if not telegram_id or not machine_type:
        return jsonify({"error": "telegram_id and machine_type required"}), 400

    position = storage.get_queue_position(normalized_house, machine_type, telegram_id)

    WAIT_TIMES = {"washer": 45, "dryer": 60}
    estimated_wait = position * WAIT_TIMES.get(machine_type, 45) if position > 0 else 0

    return jsonify({
        "house": normalized_house,
        "machine_type": machine_type,
        "position": position,
        "in_queue": position > 0,
        "estimated_wait_mins": estimated_wait
    })


def start_api():
    # Railway provides PORT env var, fallback to SENSOR_API_PORT or 5001
    import os
    port = int(os.environ.get("PORT", config.get("SENSOR_API_PORT", 5001)))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
