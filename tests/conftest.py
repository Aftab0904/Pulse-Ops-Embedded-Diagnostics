import pytest
import subprocess
import time
import os
import sys
import threading
from automation.device_client import DeviceClient
from diagnostics.system_monitor import SystemMonitor
from reports.history_db import TestHistoryDB
from reports.report_generator import ReportGenerator
from ml_engine.anomaly_detector import LogAnomalyDetector
from automation.logger import setup_logger

logger = setup_logger("TestFixture")

# Global variables to pass data between fixtures and reporting
RUN_ID = -1
TEST_METRICS = {}
CURRENT_TEST_METRICS = []
METRICS_LOCK = threading.Lock()
COLLECTING = False

def find_emulator_executable():
    """Finds the path to the device_emulator executable depending on OS."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    names = ["device_emulator", "device_emulator.exe"]
    
    # Common search paths
    search_paths = [
        base_dir,
        os.path.join(base_dir, "build"),
        os.path.join(base_dir, "build", "Debug"),
        os.path.join(base_dir, "build", "Release"),
        os.path.join(base_dir, "embedded_app"),
    ]
    
    for path in search_paths:
        for name in names:
            full_path = os.path.join(path, name)
            if os.path.exists(full_path):
                return full_path
    return None

@pytest.fixture(scope="session", autouse=True)
def run_history_db(request):
    """Initializes run summary recording in SQLite at session level."""
    global RUN_ID
    db = TestHistoryDB()
    
    # Store temporary execution status
    session_data = {
        "total": 0,
        "passed": 0,
        "failed": 0
    }
    
    yield session_data
    
    # After all tests run:
    total = session_data["total"]
    passed = session_data["passed"]
    failed = session_data["failed"]
    
    # Perform ML Anomaly check on console log
    detector = LogAnomalyDetector()
    console_log_path = "logs/device_console.log"
    anomaly_report = detector.analyze_log_file(console_log_path)
    anomaly_count = anomaly_report["anomaly_count"]
    
    # Insert run summary in SQLite
    run_id = db.insert_test_run(
        suite_name="Embedded Linux Device Suite",
        total=total,
        passed=passed,
        failed=failed,
        log_path=console_log_path,
        anomalies=anomaly_count
    )
    
    # Save test results linked to this run_id
    for test_name, metrics in TEST_METRICS.items():
        db.insert_test_result(
            run_id=run_id,
            name=test_name,
            status=metrics["status"],
            duration=metrics["duration"],
            error_msg=metrics.get("error_message"),
            cpu_avg=metrics.get("cpu_avg", 0.0),
            mem_avg=metrics.get("mem_avg", 0.0),
            temp_max=metrics.get("temp_max", 0.0)
        )
        
    logger.info(f"Test Run results persisted to SQLite (Run ID: {run_id}).")
    
    # Generate reports
    generator = ReportGenerator()
    generator.generate_json_report(run_id, "reports/summary_run_latest.json")
    generator.generate_html_report(run_id, "reports/report_run_latest.html")
    logger.info("HTML and JSON reports updated successfully.")

@pytest.fixture(scope="session")
def target_emulator():
    """Starts the target device simulator (compiled C++ binary or Python fallback script) and stops it at the end."""
    exec_path = find_emulator_executable()
    runtime_log = "logs/device_runtime.log"
    os.makedirs("logs", exist_ok=True)
    
    if exec_path:
        logger.info(f"Launching C++ target emulator from: {exec_path}")
        cmd = [exec_path, "--port", "50007", "--log", runtime_log]
    else:
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "embedded_app", "device_emulator.py")
        if os.path.exists(script_path):
            logger.info(f"C++ binary not found. Launching Python emulator fallback from: {script_path}")
            cmd = [sys.executable, script_path, "--port", "50007", "--log", runtime_log]
        else:
            logger.error("COULD NOT FIND EMULATOR (C++ binary or Python script).")
            pytest.fail("Simulator target not found.")

    # Run emulator
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Sleep to allow socket listener boot time
    time.sleep(1.2)
    
    yield proc
    
    logger.info("Terminating target emulator...")
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
    logger.info("Target emulator process terminated.")

@pytest.fixture(scope="function")
def device_client(target_emulator, run_history_db, request):
    """Connects DeviceClient to emulator, logs metrics, and updates test result databases."""
    global CURRENT_TEST_METRICS, COLLECTING
    
    client = DeviceClient()
    connected = client.connect(retries=5, delay=0.5)
    if not connected:
        pytest.fail("Failed to connect to device socket console.")
        
    # Start telemetry collector thread for this specific test
    CURRENT_TEST_METRICS = []
    COLLECTING = True
    
    def collect_metrics():
        monitor = SystemMonitor()
        while COLLECTING:
            status = client.get_status()
            if status:
                # Get emulator process metrics
                proc_m = monitor.get_target_process_metrics()
                rss_mb = proc_m.get("rss_mb", 0.0)
                
                with METRICS_LOCK:
                    CURRENT_TEST_METRICS.append({
                        "cpu": status.get("cpu_load", 0.0),
                        "temp": status.get("temperature", 0.0),
                        "mem_rss": rss_mb
                    })
            time.sleep(0.3)
            
    collector_thread = threading.Thread(target=collect_metrics, daemon=True)
    collector_thread.start()
    
    start_time = time.time()
    
    yield client
    
    # End collection
    COLLECTING = False
    collector_thread.join(timeout=1)
    duration = time.time() - start_time
    
    # Gather metrics averages
    cpu_list = [m["cpu"] for m in CURRENT_TEST_METRICS]
    temp_list = [m["temp"] for m in CURRENT_TEST_METRICS if m["temp"] > -200.0] # ignore sensor timeout timeouts
    mem_list = [m["mem_rss"] for m in CURRENT_TEST_METRICS if m["mem_rss"] > 0]
    
    cpu_avg = sum(cpu_list) / len(cpu_list) if cpu_list else 0.0
    temp_max = max(temp_list) if temp_list else 0.0
    mem_avg = sum(mem_list) / len(mem_list) if mem_list else 0.0
    
    # Check if this test failed
    # We parse the pytest outcome (passed, failed) from request.node
    failed = False
    error_message = None
    
    # Check if there are failures in request.node rep_call
    # Actually, we can hook it or check outcome on cleanup
    
    # Determine test execution status
    # Pytest stores result in request.node.rep_call.failed in some setups, or we can use custom markers.
    # An elegant way to get test result status:
    outcome = "PASSED"
    # Inspect request.node for errors or exceptions
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        outcome = "FAILED"
        error_message = str(request.node.rep_call.longrepr)
    elif hasattr(request.node, "rep_setup") and request.node.rep_setup.failed:
        outcome = "FAILED"
        error_message = str(request.node.rep_setup.longrepr)

    # Note: rep_call/rep_setup attributes are populated by pytest_runtest_makereport hook.
    # We will write a hook in conftest.py to ensure this works!
    
    test_key = request.node.name
    
    # Save metrics
    TEST_METRICS[test_key] = {
        "status": outcome,
        "duration": duration,
        "cpu_avg": cpu_avg,
        "mem_avg": mem_avg,
        "temp_max": temp_max,
        "error_message": error_message
    }
    
    # Update session run stats
    run_history_db["total"] += 1
    if outcome == "PASSED":
        run_history_db["passed"] += 1
    else:
        run_history_db["failed"] += 1

    client.close()

# Pytest hook to store test case run report states
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()
    
    # set a report attribute for each phase ("setup", "call", "teardown")
    setattr(item, "rep_" + rep.when, rep)
