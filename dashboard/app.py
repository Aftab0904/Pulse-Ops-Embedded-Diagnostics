import os
import time
import json
from flask import Flask, render_template, jsonify, Response
from reports.history_db import TestHistoryDB
from automation.device_client import DeviceClient
from diagnostics.system_monitor import SystemMonitor

app = Flask(__name__)
db = TestHistoryDB()

def get_device_client():
    client = DeviceClient()
    # Attempt to connect to check if device emulator is alive
    # We do a fast single connection attempt
    if client.connect(retries=1, delay=0.1):
        return client
    return None

@app.route("/")
def index():
    # Fetch aggregates and history
    stats = db.get_dashboard_metrics()
    recent_runs = db.get_recent_runs(limit=10)
    
    # Check if target is running and get live status
    client = get_device_client()
    device_status = "OFFLINE"
    target_telemetry = {}
    
    if client:
        device_status = "ONLINE"
        target_telemetry = client.get_status()
        client.close()
        
    return render_template(
        "index.html", 
        stats=stats, 
        recent_runs=recent_runs, 
        device_status=device_status,
        target_telemetry=target_telemetry
    )

@app.route("/api/status")
def api_status():
    client = get_device_client()
    if not client:
        return jsonify({
            "status": "OFFLINE",
            "telemetry": {}
        })
        
    telemetry = client.get_status()
    client.close()
    return jsonify({
        "status": "ONLINE",
        "telemetry": telemetry
    })

@app.route("/api/run/<int:run_id>")
def api_run_details(run_id):
    results = db.get_run_results(run_id)
    return jsonify(results)

@app.route("/api/control/reboot", methods=["POST"])
def api_control_reboot():
    client = get_device_client()
    if not client:
        return jsonify({"success": False, "message": "Target console offline"}), 503
        
    success = client.reboot()
    client.close()
    return jsonify({"success": success})

@app.route("/api/control/inject_failure/<failure_type>", methods=["POST"])
def api_control_failure(failure_type):
    client = get_device_client()
    if not client:
        return jsonify({"success": False, "message": "Target console offline"}), 503
        
    success = client.inject_failure(failure_type)
    client.close()
    return jsonify({"success": success})

@app.route("/api/logs/stream")
def api_logs_stream():
    """SSE endpoint to tail the device console log to the client."""
    def tail_log():
        log_path = "logs/device_console.log"
        # Wait up to 5s if log doesn't exist
        for _ in range(10):
            if os.path.exists(log_path):
                break
            time.sleep(0.5)
            
        if not os.path.exists(log_path):
            yield "data: [SYSTEM] Console log file not generated yet. Waiting for run...\n\n"
            return

        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            # Seek to end of file to stream only fresh lines
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.2)
                    continue
                yield f"data: {line.strip()}\n\n"

    return Response(tail_log(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
