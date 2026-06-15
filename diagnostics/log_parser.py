import re
import os
from automation.logger import setup_logger

class LogParser:
    """Parses console logs for failure signatures, exceptions, and key metrics."""
    def __init__(self, log_file_path="logs/device_console.log", config_path="configs/config.json"):
        self.logger = setup_logger("LogParser", config_path)
        self.log_file_path = log_file_path
        
        # Regex patterns for diagnostic levels and anomalies
        self.patterns = {
            "critical": re.compile(r"\[CRITICAL\]|SEGMENTATION_FAULT|OOM-killer|OUT_OF_MEMORY", re.IGNORECASE),
            "error": re.compile(r"\[ERROR\]|SENSOR_TIMEOUT|I2C bus read failure", re.IGNORECASE),
            "warning": re.compile(r"\[WARN\]|NETWORK_DELAY|latency spiked", re.IGNORECASE),
            "boot_start": re.compile(r"Device boot sequence initiated", re.IGNORECASE),
            "boot_success": re.compile(r"Device boot successful", re.IGNORECASE)
        }

        # Regex patterns for telemetry value extraction
        self.telemetry_patterns = {
            "temp": re.compile(r"TEMP_SENSOR=(-?\d+\.\d+)"),
            "cpu": re.compile(r"CPU_LOAD=(\d+\.\d+)"),
            "mem": re.compile(r"MEM_USAGE=(\d+\.\d+)"),
            "volt": re.compile(r"VOLTAGE=(\d+\.\d+)")
        }

    def parse_log_summary(self) -> dict:
        """Parses the target log file and counts warnings, errors, and statistics."""
        summary = {
            "critical_count": 0,
            "error_count": 0,
            "warning_count": 0,
            "failures": [],
            "telemetry": {
                "temperatures": [],
                "cpu_loads": [],
                "mem_usages": [],
                "voltages": []
            },
            "boot_stages": {
                "initiated": False,
                "successful": False
            }
        }

        if not os.path.exists(self.log_file_path):
            self.logger.warn(f"Log file not found: {self.log_file_path}")
            return summary

        try:
            with open(self.log_file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    # Check severity patterns
                    if self.patterns["critical"].search(line):
                        summary["critical_count"] += 1
                        summary["failures"].append(f"CRITICAL: {line.strip()}")
                    elif self.patterns["error"].search(line):
                        summary["error_count"] += 1
                        summary["failures"].append(f"ERROR: {line.strip()}")
                    elif self.patterns["warning"].search(line):
                        summary["warning_count"] += 1

                    # Check boot stages
                    if self.patterns["boot_start"].search(line):
                        summary["boot_stages"]["initiated"] = True
                    if self.patterns["boot_success"].search(line):
                        summary["boot_stages"]["successful"] = True

                    # Extract numerical telemetry values
                    for metric, pattern in self.telemetry_patterns.items():
                        match = pattern.search(line)
                        if match:
                            val = float(match.group(1))
                            if metric == "temp" and val == -999.0:
                                # Skip invalid sensor timeouts in statistical calculations
                                continue
                            if metric == "temp":
                                summary["telemetry"]["temperatures"].append(val)
                            elif metric == "cpu":
                                summary["telemetry"]["cpu_loads"].append(val)
                            elif metric == "mem":
                                summary["telemetry"]["mem_usages"].append(val)
                            elif metric == "volt":
                                summary["telemetry"]["voltages"].append(val)

            # Summarize metrics (mean, max, min)
            metrics_summary = {}
            for metric, values in summary["telemetry"].items():
                if values:
                    metrics_summary[metric] = {
                        "avg": sum(values) / len(values),
                        "max": max(values),
                        "min": min(values),
                        "count": len(values)
                    }
                else:
                    metrics_summary[metric] = {"avg": 0.0, "max": 0.0, "min": 0.0, "count": 0}
            
            summary["telemetry_summary"] = metrics_summary
        except Exception as e:
            self.logger.error(f"Error parsing log file {self.log_file_path}: {e}")

        return summary
