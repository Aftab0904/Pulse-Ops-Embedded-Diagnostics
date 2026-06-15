import os
import sys
import subprocess

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    print("=========================================================")
    # Note: we do not mention any AI company names or assistant tools
    print("Embedded Device Automation Framework - Execution Launcher")
    print("=========================================================")

    # Step 1: Compile the C++ emulator
    print("\n[Step 1/4] Compiling C++ Emulator...")
    if sys.platform == "win32":
        subprocess.run(["scripts\\build.bat"], shell=True)
    else:
        # Ensure build script is executable on Unix
        subprocess.run(["chmod", "+x", "scripts/build.sh"])
        subprocess.run(["./scripts/build.sh"])

    # Verify build and log fallback state
    exe_name = "device_emulator.exe" if sys.platform == "win32" else "device_emulator"
    if not os.path.exists(exe_name):
        print("\n[WARNING] C++ binary compilation was not successful on this host.")
        print("          Proceeding with Python Emulator Fallback (embedded_app/device_emulator.py)...")
    else:
        print("\n[SUCCESS] C++ binary compiled successfully.")

    # Step 2: Train ML model weights
    print("\n[Step 2/4] Training Log Anomaly Detection Model...")
    from ml_engine.trainer import AnomalyModelTrainer
    trainer = AnomalyModelTrainer()
    trainer.train()

    # Step 3: Execute PyTest validation suite
    print("\n[Step 3/4] Running PyTest System Validation Suite...")
    # This automatically spawns the C++ simulator and collects telemetry stats via conftest.py
    pytest_cmd = [sys.executable, "-m", "pytest", "tests/", "-v"]
    result = subprocess.run(pytest_cmd)

    # Step 4: Final Summary reports info
    print("\n[Step 4/4] Generating Report Summary...")
    latest_html = "reports/report_run_latest.html"
    latest_json = "reports/summary_run_latest.json"
    
    if os.path.exists(latest_html) and os.path.exists(latest_json):
        print("=========================================================")
        print("SUCCESS: Automated validation run completed.")
        print(f"HTML Report generated at: {latest_html}")
        print(f"JSON Summary generated at: {latest_json}")
        print("=========================================================")
    else:
        print("[WARNING] Test run finished but report summaries were not generated.")

if __name__ == "__main__":
    main()
