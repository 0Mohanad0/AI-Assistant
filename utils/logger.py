import json
import os
from datetime import datetime


def log_user_data(username, entry):

    log_path = f"users/{username}/logs.json"

    if not os.path.exists(log_path):
        logs = []
    else:
        with open(log_path, "r") as f:
            logs = json.load(f)

    logs.append({
        "timestamp": str(datetime.now()),
        "entry": entry
    })

    with open(log_path, "w") as f:
        json.dump(logs, f, indent=4)


def read_logs(username):

    log_path = f"users/{username}/logs.json"

    if not os.path.exists(log_path):
        return []

    with open(log_path, "r") as f:
        return json.load(f)
