import os
import json
import base64
from datetime import datetime
from reports.history_db import TestHistoryDB
from automation.logger import setup_logger

class ReportGenerator:
    """Generates standalone HTML reports and structured JSON summaries of validation runs."""
    def __init__(self, config_path="configs/config.json"):
        self.logger = setup_logger("ReportGenerator", config_path)
        self.db = TestHistoryDB(config_path)

    def generate_json_report(self, run_id: int, output_path: str):
        """Generates a JSON execution report from database metrics."""
        results = self.db.get_run_results(run_id)
        runs = self.db.get_recent_runs(limit=100)
        run_data = next((r for r in runs if r["id"] == run_id), None)
        
        if not run_data:
            self.logger.error(f"Cannot generate JSON report: Run ID {run_id} not found.")
            return

        report_data = {
            "run_id": run_id,
            "timestamp": run_data["timestamp"],
            "suite_name": run_data["suite_name"],
            "summary": {
                "total": run_data["total_tests"],
                "passed": run_data["passed_tests"],
                "failed": run_data["failed_tests"],
                "success_rate": (run_data["passed_tests"] / run_data["total_tests"] * 100) if run_data["total_tests"] > 0 else 0
            },
            "anomaly_count": run_data["anomaly_count"],
            "tests": results
        }

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=4)
            self.logger.info(f"JSON execution report generated: {output_path}")
        except Exception as e:
            self.logger.error(f"Failed to generate JSON report: {e}")

    def generate_html_report(self, run_id: int, output_path: str, anomaly_chart_path="reports/anomaly_profile.png"):
        """Generates a self-contained premium HTML test execution report."""
        results = self.db.get_run_results(run_id)
        runs = self.db.get_recent_runs(limit=100)
        run_data = next((r for r in runs if r["id"] == run_id), None)

        if not run_data:
            self.logger.error(f"Cannot generate HTML report: Run ID {run_id} not found.")
            return

        # Base64 encode the anomaly chart if it exists
        chart_base64 = ""
        if os.path.exists(anomaly_chart_path):
            try:
                with open(anomaly_chart_path, "rb") as f:
                    chart_base64 = base64.b64encode(f.read()).decode("utf-8")
            except Exception as e:
                self.logger.error(f"Failed to base64 encode anomaly chart: {e}")

        # HTML generation
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        passed = run_data["passed_tests"]
        failed = run_data["failed_tests"]
        total = run_data["total_tests"]
        success_rate = (passed / total * 100) if total > 0 else 0
        anomaly_count = run_data["anomaly_count"]

        # Stylized Rows for individual tests
        test_rows = ""
        for t in results:
            status_cls = "status-pass" if t["status"] == "PASSED" else "status-fail"
            err_msg = f"<div class='error-msg'>{t['error_message']}</div>" if t['error_message'] else ""
            test_rows += f"""
            <tr class="test-row">
                <td class="test-name font-semibold">{t['name']}</td>
                <td><span class="status-pill {status_cls}">{t['status']}</span></td>
                <td class="mono">{t['duration']:.3f}s</td>
                <td class="mono">{t['cpu_avg']:.1f}%</td>
                <td class="mono">{t['mem_avg']:.1f} MB</td>
                <td class="mono">{t['temp_max']:.1f}°C</td>
                <td>{err_msg}</td>
            </tr>
            """

        chart_section = ""
        if chart_base64:
            chart_section = f"""
            <div class="card chart-card">
                <h2>ML Anomaly Score Mapping</h2>
                <p class="subtitle">Isolation Forest Decision Profile for target logs</p>
                <div class="chart-container">
                    <img src="data:image/png;base64,{chart_base64}" alt="Anomaly Profile Chart">
                </div>
            </div>
            """

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Embedded Test Report - Run #{run_id}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0a0f1d;
            --bg-secondary: #121829;
            --bg-tertiary: #1b233a;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --primary: #00d2ff;
            --secondary: #ff007f;
            --success: #10b981;
            --success-glow: rgba(16, 185, 129, 0.15);
            --fail: #ef4444;
            --fail-glow: rgba(239, 68, 68, 0.15);
            --border: #2e374f;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-main);
            line-height: 1.6;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        header {{
            margin-bottom: 40px;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            border-bottom: 1px solid var(--border);
            padding-bottom: 20px;
        }}
        h1 {{
            font-size: 2.2rem;
            font-weight: 700;
            letter-spacing: -0.05em;
            color: #ffffff;
            margin-bottom: 5px;
        }}
        .subtitle {{
            font-size: 0.95rem;
            color: var(--text-muted);
        }}
        .meta-timestamp {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9rem;
            color: var(--primary);
        }}
        /* Stats Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .card {{
            background-color: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            position: relative;
            overflow: hidden;
        }}
        .card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: var(--primary);
        }}
        .stat-value {{
            font-size: 2.5rem;
            font-weight: 700;
            line-height: 1;
            margin: 10px 0 5px;
            font-family: 'JetBrains Mono', monospace;
        }}
        .stat-label {{
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            font-weight: 500;
        }}
        /* Colors for Stats */
        .card.passed::before {{ background: var(--success); }}
        .card.passed .stat-value {{ color: var(--success); }}
        .card.failed::before {{ background: var(--fail); }}
        .card.failed .stat-value {{ color: var(--fail); }}
        .card.anomalies::before {{ background: var(--secondary); }}
        .card.anomalies .stat-value {{ color: var(--secondary); }}
        
        /* Table styles */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 40px;
            background-color: var(--bg-secondary);
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border);
        }}
        th, td {{
            padding: 16px 20px;
            text-align: left;
        }}
        th {{
            background-color: var(--bg-tertiary);
            font-weight: 600;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            border-bottom: 1px solid var(--border);
        }}
        td {{
            border-bottom: 1px solid var(--border);
            font-size: 0.95rem;
        }}
        .test-row:last-child td {{
            border-bottom: none;
        }}
        .test-row:hover {{
            background-color: rgba(255, 255, 255, 0.02);
        }}
        .font-semibold {{
            font-weight: 600;
        }}
        .mono {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9rem;
        }}
        .status-pill {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 600;
            letter-spacing: 0.03em;
        }}
        .status-pass {{
            background-color: var(--success-glow);
            color: var(--success);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}
        .status-fail {{
            background-color: var(--fail-glow);
            color: var(--fail);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}
        .error-msg {{
            font-family: 'JetBrains Mono', monospace;
            color: var(--fail);
            font-size: 0.8rem;
            background-color: rgba(239, 68, 68, 0.05);
            padding: 8px 12px;
            border-radius: 6px;
            border-left: 3px solid var(--fail);
            margin-top: 5px;
            white-space: pre-wrap;
        }}
        /* Chart Card */
        .chart-card {{
            margin-bottom: 40px;
        }}
        .chart-card::before {{
            background: linear-gradient(to bottom, var(--primary), var(--secondary));
        }}
        .chart-container {{
            width: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            margin-top: 20px;
            background-color: var(--bg-primary);
            border-radius: 8px;
            padding: 10px;
            border: 1px solid var(--border);
        }}
        .chart-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 6px;
        }}
        footer {{
            text-align: center;
            font-size: 0.8rem;
            color: var(--text-muted);
            border-top: 1px solid var(--border);
            padding-top: 20px;
            margin-top: 60px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>Validation Execution Report</h1>
                <div class="subtitle">Suite: {run_data["suite_name"]} | Run Reference: #{run_id}</div>
            </div>
            <div class="meta-timestamp">Report Generated: {now_str}</div>
        </header>

        <section class="stats-grid">
            <div class="card">
                <div class="stat-label">Total Executed</div>
                <div class="stat-value">{total}</div>
                <p class="subtitle">Test cases completed</p>
            </div>
            <div class="card passed">
                <div class="stat-label">Passed</div>
                <div class="stat-value">{passed}</div>
                <p class="subtitle">Validation checks met</p>
            </div>
            <div class="card failed">
                <div class="stat-label">Failed</div>
                <div class="stat-value">{failed}</div>
                <p class="subtitle">Unmet assertions</p>
            </div>
            <div class="card anomalies">
                <div class="stat-label">ML Anomalies</div>
                <div class="stat-value">{anomaly_count}</div>
                <p class="subtitle">Outlier log segments</p>
            </div>
        </section>

        <section class="card" style="padding: 0; margin-bottom: 40px; overflow: hidden; border-radius: 12px;">
            <div style="padding: 24px 24px 10px 24px;">
                <h2 style="font-size: 1.4rem;">Test Case Execution Metrics</h2>
                <p class="subtitle">Granular process statistics of target simulator during each check</p>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Test Case Name</th>
                        <th>Status</th>
                        <th>Duration</th>
                        <th>Avg CPU</th>
                        <th>Avg RSS</th>
                        <th>Max Temp</th>
                        <th>Diagnostics / Failures</th>
                    </tr>
                </thead>
                <tbody>
                    {test_rows}
                </tbody>
            </table>
        </section>

        {chart_section}

        <footer>
            <p>Embedded Linux Device Automation Framework - System Validation Telemetry Output</p>
        </footer>
    </div>
</body>
</html>
"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            self.logger.info(f"Self-contained HTML execution report generated: {output_path}")
        except Exception as e:
            self.logger.error(f"Failed to generate HTML report: {e}")
            
if __name__ == "__main__":
    # Test generation
    gen = ReportGenerator()
    # If run 1 exists, try it
    gen.generate_json_report(1, "reports/summary_run_1.json")
    gen.generate_html_report(1, "reports/report_run_1.html")
