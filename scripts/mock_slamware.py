from fastapi import FastAPI
import time
import threading

app = FastAPI()

ACTION_DB = {}
ACTION_ID = 0
LOCK = threading.Lock()


@app.get("/api/core/system/v1/power/status")
def power_status():
    return {
        "batteryPercentage": 80,
        "powerStage": "running",
        "isCharging": False
    }


@app.get("/api/multi-floor/map/v1/pois")
def pois():
    return [
        {"poi_name": "POI1", "floor": "1F"},
        {"poi_name": "POI2", "floor": "1F"},
    ]


@app.post("/api/core/motion/v1/actions")
def create_action(payload: dict):
    global ACTION_ID
    with LOCK:
        ACTION_ID += 1
        aid = ACTION_ID
        ACTION_DB[aid] = {
            "start": time.time(),
            "status": "RUNNING",
            "target": payload["options"]["target"]["poi_name"]
        }
    return {"action_id": aid}


@app.get("/api/core/motion/v1/actions/{action_id}")
def get_action(action_id: int):
    a = ACTION_DB.get(action_id)
    if not a:
        return {}

    elapsed = time.time() - a["start"]
    if elapsed > 3:
        return {
            "stage": "COMPLETED",
            "state": {"result": 0, "reason": ""}
        }

    return {
        "stage": "RUNNING",
        "state": {"result": 0, "reason": ""}
    }


@app.delete("/api/core/motion/v1/actions/:current")
def cancel_action():
    return {}
