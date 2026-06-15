import time
from automation.test_runner import TestRunner

runner = TestRunner()

@runner.test_case(name="Network Delay Injection", description="Validates interface handling under network delay alerts")
def test_network_delay_injection(device_client):
    device_client.reboot()
    time.sleep(1.5)
    
    # Inject network delay
    assert device_client.inject_failure("NETWORK_DELAY") is True
    time.sleep(1.0)
    
    # Check status
    status = device_client.get_status()
    assert status["active_failure"] == "NETWORK_DELAY"
    
    # Assert dmesg/system warning logging
    log_file = device_client.device_log_file
    with open(log_file, "r") as f:
        log_content = f.read()
        
    assert "NETWORK_DELAY: Virtual interface eth0 packet latency spiked" in log_content
    
    # Restore target
    device_client.reboot()
