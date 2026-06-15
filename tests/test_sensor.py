import time
from automation.test_runner import TestRunner

runner = TestRunner()

@runner.test_case(name="Telemetry Bounds Checks", description="Verifies CPU, temperature and voltage are within safe ranges")
def test_nominal_telemetry_bounds(device_client):
    # Wait for target to be ready
    time.sleep(1.0)
    
    status = device_client.get_status()
    assert status, "Failed to query status telemetry from target emulator"
    
    # Assert nominal bounds
    assert 20.0 <= status["cpu_load"] <= 38.0, f"Unexpected CPU load: {status['cpu_load']}"
    assert 34.0 <= status["temperature"] <= 44.0, f"Unexpected temperature: {status['temperature']}"
    assert 1.15 <= status["voltage"] <= 1.25, f"Unexpected voltage: {status['voltage']}"

@runner.test_case(name="Sensor Failure Diagnostic", description="Injects SENSOR_TIMEOUT and asserts error reports")
def test_sensor_timeout_injection(device_client):
    # Ensure nominal starting state
    device_client.reboot()
    time.sleep(1.5)
    
    # Inject failure
    assert device_client.inject_failure("SENSOR_TIMEOUT") is True
    time.sleep(1.0)
    
    # Check current status
    status = device_client.get_status()
    assert status["temperature"] == -999.0, f"Temperature should be flagged -999.0 on timeout, got: {status['temperature']}"
    assert status["active_failure"] == "SENSOR_TIMEOUT"
    
    # Read console log file to verify error message was printed
    log_file = device_client.device_log_file
    with open(log_file, "r") as f:
        log_content = f.read()
        
    assert "SENSOR_TIMEOUT: I2C bus read failure" in log_content
    
    # Reboot to restore nominal state
    device_client.reboot()
