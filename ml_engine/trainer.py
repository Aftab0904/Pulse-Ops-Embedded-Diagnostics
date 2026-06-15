import os
import pickle
import random
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import IsolationForest
from automation.logger import setup_logger

class AnomalyModelTrainer:
    """Generates synthetic baseline logs and trains the IsolationForest classifier."""
    def __init__(self, config_path="configs/config.json"):
        self.logger = setup_logger("ModelTrainer", config_path)
        self.config_path = config_path
        
        # Load configuration details
        self.model_path = "ml_engine/models/anomaly_detector.pkl"
        self.vectorizer_path = "ml_engine/models/tfidf_vectorizer.pkl"
        self.training_size = 2000
        
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                    self.model_path = cfg.get("ml", {}).get("model_path", self.model_path)
                    self.vectorizer_path = cfg.get("ml", {}).get("vectorizer_path", self.vectorizer_path)
                    self.training_size = cfg.get("ml", {}).get("training_data_size", self.training_size)
            except Exception:
                pass

    def generate_synthetic_logs(self) -> list[str]:
        """Generates representative normal logs and sparse anomalies for model baseline training."""
        normal_templates = [
            "Telemetry update -> TEMP_SENSOR={temp:.2f} CPU_LOAD={cpu:.2f} MEM_USAGE={mem:.2f} VOLTAGE={volt:.2f}",
            "Device boot sequence initiated.",
            "Bootloader version 2026.06.15-g10a5e89b9 loading...",
            "Linux version 6.1.0-21-amd64 (GCC version 12.2.0) bootstraping...",
            "Initializing RAM config: 512MB LPDDR4 detected.",
            "dmesg: [0.000000] Booting CPU 0x00 [hardware id 0x0]",
            "Starting systemd init system (v252.22)...",
            "Starting networking service: dhcpd...",
            "Starting telemetry daemon: pulse-ops-agent...",
            "Device boot successful. System enters READY state.",
            "System reset/reboot command received."
        ]

        anomaly_templates = [
            "Failure injected: MEMORY_LEAK. Target system memory consumption will rise.",
            "Failure injected: SENSOR_TIMEOUT. Primary sensor communication interrupted.",
            "Failure injected: NETWORK_DELAY. Virtual interfaces report high latency.",
            "Failure injected: SEGFAULT. Simulating memory access violation.",
            "SEGMENTATION_FAULT: Invalid read/write at address 0x0000000C (Signal 11)",
            "MEMORY_CORRUPTION: Heap overflow detected in telemetry process.",
            "KERNEL_OUT_OF_MEMORY: systemd-oomd triggered.",
            "KERNEL_OUT_OF_MEMORY: OOM-killer invoked.",
            "SENSOR_TIMEOUT: I2C bus read failure. Expected sensor address 0x48 unresponsive.",
            "NETWORK_DELAY: Virtual interface eth0 packet latency spiked (350ms)."
        ]

        logs = []
        
        # 95% Normal logs
        normal_count = int(self.training_size * 0.96)
        for _ in range(normal_count):
            tpl = random.choice(normal_templates)
            if "Telemetry update" in tpl:
                log_msg = tpl.format(
                    temp=random.uniform(35.0, 42.0),
                    cpu=random.uniform(20.0, 35.0),
                    mem=random.uniform(24.0, 28.0),
                    volt=random.uniform(1.19, 1.21)
                )
            else:
                log_msg = tpl
            
            level = "INFO"
            if "reboot" in log_msg:
                level = "WARN"
            logs.append(f"[2026-06-15 12:00:00.000] [{level}] {log_msg}")

        # 4% Anomalous logs
        anomaly_count = self.training_size - normal_count
        for _ in range(anomaly_count):
            log_msg = random.choice(anomaly_templates)
            level = "ERROR"
            if "SEGFAULT" in log_msg or "MEMORY_CORRUPTION" in log_msg or "OOM-killer" in log_msg:
                level = "CRITICAL"
            elif "DELAY" in log_msg or "LEAK" in log_msg:
                level = "WARN"
            logs.append(f"[2026-06-15 12:00:00.000] [{level}] {log_msg}")

        random.shuffle(logs)
        return logs

    def train(self):
        """Trains the model and serializes weights."""
        self.logger.info("Starting ML Anomaly model training...")
        
        # 1. Generate logs
        raw_logs = self.generate_synthetic_logs()
        self.logger.info(f"Generated {len(raw_logs)} synthetic log entries for training.")

        # 2. Extract features using TF-IDF
        # We strip timestamps to focus purely on text context and level
        processed_logs = []
        for log in raw_logs:
            # Strip timestamp e.g. [2026-06-15 12:00:00.000]
            parts = log.split("] ", 1)
            if len(parts) > 1:
                processed_logs.append(parts[1])
            else:
                processed_logs.append(log)

        vectorizer = TfidfVectorizer(max_features=120, stop_words=None, token_pattern=r"(?u)\b\w+\b")
        vectors = vectorizer.fit_transform(processed_logs)
        
        # Convert to dense array
        x_train = vectors.toarray()

        # 3. Fit IsolationForest
        # We use a small contamination to represent the noise
        model = IsolationForest(n_estimators=100, contamination=0.04, random_state=42)
        model.fit(x_train)
        
        # Evaluate training predictions
        preds = model.predict(x_train)
        anomalies_detected = list(preds).count(-1)
        self.logger.info(f"Model fitted successfully. Detected {anomalies_detected} anomalies in training set.")

        # 4. Serialize model and vectorizer
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.vectorizer_path), exist_ok=True)

        with open(self.model_path, "wb") as f:
            pickle.dump(model, f)
        with open(self.vectorizer_path, "wb") as f:
            pickle.dump(vectorizer, f)

        self.logger.info(f"Model saved to: {self.model_path}")
        self.logger.info(f"Vectorizer saved to: {self.vectorizer_path}")
        return True

if __name__ == "__main__":
    trainer = AnomalyModelTrainer()
    trainer.train()
