import psutil
import time
from automation.logger import setup_logger

class SystemMonitor:
    """Monitors target system load and detailed memory footprint of the device process."""
    def __init__(self, target_process_name="device_emulator", config_path="configs/config.json"):
        self.logger = setup_logger("SystemMonitor", config_path)
        self.target_name = target_process_name

    def get_system_stats(self) -> dict:
        """Collects overall host system statistics."""
        try:
            return {
                "cpu_percent": psutil.cpu_percent(interval=None),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
                "timestamp": time.time()
            }
        except Exception as e:
            self.logger.error(f"Failed to fetch overall system stats: {e}")
            return {}

    def find_target_process(self):
        """Locates the target process by name and returns its psutil.Process object."""
        # Check both Windows and Linux executable extensions
        names_to_check = [self.target_name, f"{self.target_name}.exe"]
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] in names_to_check:
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return None

    def get_target_process_metrics(self) -> dict:
        """Gathers granular process-level performance metrics of the device simulation."""
        proc = self.find_target_process()
        if not proc:
            return {"status": "DEAD", "cpu_percent": 0.0, "rss_mb": 0.0, "threads": 0}

        try:
            # Under Windows, first call to cpu_percent returns 0.0
            cpu = proc.cpu_percent(interval=None)
            mem_info = proc.memory_info()
            rss_mb = mem_info.rss / (1024 * 1024)
            num_threads = proc.num_threads()
            
            return {
                "status": "RUNNING",
                "pid": proc.pid,
                "cpu_percent": cpu,
                "rss_mb": rss_mb,
                "threads": num_threads,
                "timestamp": time.time()
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {"status": "CRASHED", "cpu_percent": 0.0, "rss_mb": 0.0, "threads": 0}

    def check_memory_leak_growth(self, duration_sec=5, sample_interval_sec=1) -> float:
        """Measures memory growth rate (in MB/sec) of the target process over a duration."""
        self.logger.info(f"Monitoring process memory growth for {duration_sec}s...")
        metrics_start = self.get_target_process_metrics()
        if metrics_start.get("status") != "RUNNING":
            self.logger.warn("Target process not running; cannot monitor memory growth.")
            return 0.0

        start_rss = metrics_start["rss_mb"]
        time.sleep(duration_sec)
        
        metrics_end = self.get_target_process_metrics()
        if metrics_end.get("status") != "RUNNING":
            self.logger.error("Target process crashed during memory leak inspection.")
            return -1.0 # Process crashed
            
        end_rss = metrics_end["rss_mb"]
        growth = end_rss - start_rss
        growth_rate = growth / duration_sec
        self.logger.info(f"Target process memory growth: {growth:.3f} MB in {duration_sec}s ({growth_rate:.3f} MB/s)")
        return growth_rate
