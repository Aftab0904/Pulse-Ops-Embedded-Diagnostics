import os
import pickle
import json
import numpy as np
import matplotlib
matplotlib.use('Agg') # Thread-safe headless backend for web server and testing
import matplotlib.pyplot as plt
from automation.logger import setup_logger

class LogAnomalyDetector:
    """Classifies log lines using Isolation Forest to highlight suspicious telemetry patterns."""
    def __init__(self, config_path="configs/config.json"):
        self.logger = setup_logger("AnomalyDetector", config_path)
        self.config_path = config_path
        
        # Load configuration details
        self.model_path = "ml_engine/models/anomaly_detector.pkl"
        self.vectorizer_path = "ml_engine/models/tfidf_vectorizer.pkl"
        self.anomaly_threshold = -0.15
        
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                    self.model_path = cfg.get("ml", {}).get("model_path", self.model_path)
                    self.vectorizer_path = cfg.get("ml", {}).get("vectorizer_path", self.vectorizer_path)
                    self.anomaly_threshold = cfg.get("ml", {}).get("anomaly_threshold", self.anomaly_threshold)
            except Exception:
                pass

        self.model = None
        self.vectorizer = None
        self.load_model()

    def load_model(self):
        """Loads model weights. Automatically triggers training if not found."""
        if not os.path.exists(self.model_path) or not os.path.exists(self.vectorizer_path):
            self.logger.warn("Model weights missing. Invoking model training pipeline...")
            from ml_engine.trainer import AnomalyModelTrainer
            trainer = AnomalyModelTrainer(self.config_path)
            trainer.train()

        try:
            with open(self.model_path, "rb") as f:
                self.model = pickle.load(f)
            with open(self.vectorizer_path, "rb") as f:
                self.vectorizer = pickle.load(f)
            self.logger.info("ML Anomaly detector models loaded successfully.")
        except Exception as e:
            self.logger.error(f"Failed to load ML models: {e}")

    def predict_log(self, log_line: str) -> tuple[int, float]:
        """Classifies a single log line.

        Returns:
            label: 1 if normal, -1 if anomalous.
            score: The raw decision function score (more negative = more anomalous).
        """
        if not self.model or not self.vectorizer:
            return 1, 0.0

        try:
            # Strip timestamp and formatting brackets to isolate core message
            parts = log_line.split("] ", 1)
            text_to_vectorize = parts[1] if len(parts) > 1 else log_line

            # Vectorize
            vec = self.vectorizer.transform([text_to_vectorize]).toarray()
            
            # Predict
            pred = self.model.predict(vec)[0]
            score = self.model.decision_function(vec)[0]
            
            # If score is below user-defined threshold, flag it as anomaly
            if score < self.anomaly_threshold:
                pred = -1

            return int(pred), float(score)
        except Exception as e:
            # Fallback on parse errors
            return 1, 0.0

    def analyze_log_file(self, log_file_path: str, output_image_dir="reports") -> dict:
        """Parses a log file, tags anomalies, and plots log anomaly profiles."""
        report = {
            "total_lines": 0,
            "anomaly_count": 0,
            "anomalies": [],
            "scores": [],
            "timestamps": []
        }

        if not os.path.exists(log_file_path):
            self.logger.error(f"Log file not found for analysis: {log_file_path}")
            return report

        try:
            with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
                for idx, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                        
                    report["total_lines"] += 1
                    pred, score = self.predict_log(line)
                    
                    # Store data
                    report["scores"].append(score)
                    report["timestamps"].append(idx)
                    
                    if pred == -1:
                        report["anomaly_count"] += 1
                        report["anomalies"].append({
                            "line_num": idx + 1,
                            "content": line,
                            "score": score
                        })

            # Generate modern dark mode chart of logs anomaly profile
            if report["scores"]:
                self.plot_anomaly_scores(report["scores"], output_image_dir)
                
        except Exception as e:
            self.logger.error(f"Error executing file anomaly analysis: {e}")

        return report

    def plot_anomaly_scores(self, scores: list[float], output_dir: str):
        """Plots log anomaly scores using a sleek, premium dark-themed layout."""
        os.makedirs(output_dir, exist_ok=True)
        img_path = os.path.join(output_dir, "anomaly_profile.png")

        try:
            # Set styled dark parameters
            plt.style.use('dark_background')
            fig, ax = plt.subplots(figsize=(10, 4))
            
            x = np.arange(len(scores))
            y = np.array(scores)
            
            # Plot baseline
            ax.plot(x, y, color="#00d2ff", label="Decision Score", linewidth=1.5, alpha=0.8)
            
            # Highlight threshold line
            ax.axhline(y=self.anomaly_threshold, color="#ff007f", linestyle="--", label="Anomaly Threshold", alpha=0.9)
            
            # Highlight points below threshold
            anomalies_idx = np.where(y < self.anomaly_threshold)[0]
            if len(anomalies_idx) > 0:
                ax.scatter(anomalies_idx, y[anomalies_idx], color="#ff007f", s=30, zorder=5, label="Detected Anomalies")
                
            ax.set_title("Log Stream Anomaly Profile", fontsize=12, fontweight="bold", pad=15)
            ax.set_xlabel("Log Entry Sequence Index", fontsize=10)
            ax.set_ylabel("Decision Score", fontsize=10)
            ax.grid(True, linestyle=":", alpha=0.3)
            ax.legend(loc="upper right", framealpha=0.8)
            
            plt.tight_layout()
            plt.savefig(img_path, dpi=150)
            plt.close()
            self.logger.info(f"Anomaly profile chart saved to {img_path}")
        except Exception as e:
            self.logger.error(f"Failed to plot anomaly scores: {e}")
