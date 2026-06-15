import time
import json
import os
from automation.test_runner import TestRunner
from diagnostics.system_monitor import SystemMonitor

runner = TestRunner()

@runner.test_case(name="System Resource stress validation", description="Verifies system telemetry remains under thresholds")
def test_system_resource_thresholds(device_client):
    # Load config thresholds
    max_cpu = 85.0
    max_mem = 80.0
    
    config_path = "configs/config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
                max_cpu = cfg.get("thresholds", {}).get("max_cpu_percent", max_cpu)
                max_mem = cfg.get("thresholds", {}).get("max_memory_percent", max_mem)
        except Exception:
            pass

    monitor = SystemMonitor()
    
    # Check overall host metrics
    host_stats = monitor.get_system_stats()
    assert host_stats, "Failed to gather host system performance metrics"
    
    assert host_stats["cpu_percent"] < max_cpu, f"Host overall CPU load exceeds threshold: {host_stats['cpu_percent']}% (Limit: {max_cpu}%)"
    assert host_stats["memory_percent"] < max_mem, f"Host memory consumption exceeds threshold: {host_stats['memory_percent']}% (Limit: {max_mem}%)"

    # Query target status
    status = device_client.get_status()
    assert status, "Target emulator status not queryable"
    
    # Assert target internal values are healthy
    assert status["cpu_load"] < max_cpu, f"Target report CPU load exceeds threshold: {status['cpu_load']}%"
    assert status["mem_usage"] < max_mem, f"Target report MEM usage exceeds threshold: {status['mem_usage']}%"
