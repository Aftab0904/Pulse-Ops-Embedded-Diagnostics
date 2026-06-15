import sqlite3
import os
import json
from datetime import datetime
from automation.logger import setup_logger

class TestHistoryDB:
    """Manages SQLite connection and schema to record validation run summaries."""
    def __init__(self, config_path="configs/config.json"):
        self.logger = setup_logger("TestHistoryDB", config_path)
        self.db_path = "reports/test_history.db"

        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                    self.db_path = cfg.get("database", {}).get("db_path", self.db_path)
            except Exception:
                pass

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """Creates test history tables if they do not exist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Test run summary table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS test_runs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        suite_name TEXT NOT NULL,
                        total_tests INTEGER NOT NULL,
                        passed_tests INTEGER NOT NULL,
                        failed_tests INTEGER NOT NULL,
                        log_file_path TEXT,
                        anomaly_count INTEGER DEFAULT 0
                    )
                """)

                # Individual test case results
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS test_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        duration REAL NOT NULL,
                        error_message TEXT,
                        cpu_avg REAL DEFAULT 0.0,
                        mem_avg REAL DEFAULT 0.0,
                        temp_max REAL DEFAULT 0.0,
                        FOREIGN KEY (run_id) REFERENCES test_runs(id) ON DELETE CASCADE
                    )
                """)
                conn.commit()
            self.logger.info("SQLite Test History Database initialized.")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")

    def insert_test_run(self, suite_name: str, total: int, passed: int, failed: int, log_path: str, anomalies: int) -> int:
        """Saves a run summary and returns the inserted run_id."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO test_runs (timestamp, suite_name, total_tests, passed_tests, failed_tests, log_file_path, anomaly_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, suite_name, total, passed, failed, log_path, anomalies))
                conn.commit()
                run_id = cursor.lastrowid
                self.logger.debug(f"Inserted test run ID: {run_id}")
                return run_id
        except Exception as e:
            self.logger.error(f"Failed to save test run: {e}")
            return -1

    def insert_test_result(self, run_id: int, name: str, status: str, duration: float, error_msg: str = None, cpu_avg=0.0, mem_avg=0.0, temp_max=0.0):
        """Saves an individual test case's metrics."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO test_results (run_id, name, status, duration, error_message, cpu_avg, mem_avg, temp_max)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (run_id, name, status, duration, error_msg, cpu_avg, mem_avg, temp_max))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to save test result for {name}: {e}")

    def get_recent_runs(self, limit=10) -> list[dict]:
        """Fetches the most recent test runs."""
        runs = []
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM test_runs ORDER BY id DESC LIMIT ?", (limit,))
                for row in cursor.fetchall():
                    runs.append(dict(row))
        except Exception as e:
            self.logger.error(f"Failed to fetch recent runs: {e}")
        return runs

    def get_run_results(self, run_id: int) -> list[dict]:
        """Fetches all test case results associated with a run ID."""
        results = []
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM test_results WHERE run_id = ?", (run_id,))
                for row in cursor.fetchall():
                    results.append(dict(row))
        except Exception as e:
            self.logger.error(f"Failed to fetch results for run {run_id}: {e}")
        return results

    def get_dashboard_metrics(self) -> dict:
        """Computes aggregate historical statistics for the Flask dashboard."""
        metrics = {
            "total_runs": 0,
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "success_rate": 100.0,
            "total_anomalies": 0
        }
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*), SUM(total_tests), SUM(passed_tests), SUM(failed_tests), SUM(anomaly_count) FROM test_runs")
                row = cursor.fetchone()
                if row and row[0] > 0:
                    metrics["total_runs"] = row[0]
                    metrics["total_tests"] = row[1] or 0
                    metrics["passed_tests"] = row[2] or 0
                    metrics["failed_tests"] = row[3] or 0
                    metrics["total_anomalies"] = row[4] or 0
                    
                    if metrics["total_tests"] > 0:
                        metrics["success_rate"] = (metrics["passed_tests"] / metrics["total_tests"]) * 100
        except Exception as e:
            self.logger.error(f"Failed to fetch aggregate metrics: {e}")
        return metrics
