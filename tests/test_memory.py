import time
from automation.test_runner import TestRunner
from diagnostics.system_monitor import SystemMonitor

runner = TestRunner()

@runner.test_case(name="Memory Leak Diagnostic", description="Monitors target process memory growth during leak injection")
def test_target_memory_leak(device_client):
    device_client.reboot()
    time.sleep(1.5)
    
    monitor = SystemMonitor()
    
    # Check baseline growth (should be roughly 0.0)
    baseline_growth = monitor.check_memory_leak_growth(duration_sec=3, sample_interval_sec=1)
    assert baseline_growth < 0.05, f"Expected stable baseline memory footprint, got growth: {baseline_growth:.3f} MB/s"
    
    # Inject memory leak failure
    assert device_client.inject_failure("MEMORY_LEAK") is True
    time.sleep(0.5)
    
    # Measure memory growth rate
    leak_growth = monitor.check_memory_leak_growth(duration_sec=3, sample_interval_sec=1)
    
    # Assert memory growth rate is significant
    assert leak_growth > 0.05, f"Expected significant memory growth after injection, got rate: {leak_growth:.3f} MB/s"
    
    # Reboot to stop memory leak
    device_client.reboot()
