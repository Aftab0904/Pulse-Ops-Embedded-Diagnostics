import time
from automation.test_runner import TestRunner, TestFailureException

runner = TestRunner()

@runner.test_case(name="Boot Sequence Validation", description="Verifies correct boot transitions and timings", retries=2)
def test_device_boot_sequence(device_client):
    # Trigger reboot
    assert device_client.reboot() is True
    
    # Track boot time and stages
    stages_seen = []
    start_time = time.time()
    booted = False
    
    # Poll status for transitions
    while time.time() - start_time < 6.0:
        status = device_client.get_status()
        if not status:
            time.sleep(0.2)
            continue
            
        stage = status.get("boot_stage")
        if stage and stage not in stages_seen:
            stages_seen.append(stage)
            
        if stage == "READY":
            booted = True
            break
        time.sleep(0.2)

    # Performance boundary checks
    boot_duration = time.time() - start_time
    assert booted, f"Device failed to reach READY state. Stages reached: {stages_seen}"
    assert boot_duration < 8.0, f"Device boot took too long: {boot_duration:.2f}s"
    
    # Check that it traversed main stages
    assert "BOOTLOADER" in stages_seen
    assert "KERNEL_INIT" in stages_seen
    assert "SERVICES_START" in stages_seen
    
    # Parse logs to assert landmark log tags
    # Let's inspect the console log file
    log_file = device_client.device_log_file
    with open(log_file, "r") as f:
        log_content = f.read()
        
    assert "Device boot sequence initiated" in log_content
    assert "Bootloader version" in log_content
    assert "Linux version" in log_content
    assert "Starting systemd init system" in log_content
    assert "Device boot successful. System enters READY state" in log_content
