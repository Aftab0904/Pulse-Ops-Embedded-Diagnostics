# Embedded Linux Device Automation & Diagnostics Framework

A production-style, end-to-end Hardware-in-the-Loop (HIL) simulation and system validation framework. This repository integrates a multithreaded **C++ Device Emulator** (target system simulator) with a **Python Automation Core** (validation tests, diagnostics, and SSH communication) and an **ML-based Anomaly Engine** (IsolationForest log parsing). It is designed to model validation pipelines used in major semiconductor and telecommunications hardware testing environments.

---

## 🏗️ Architecture & Data Flow

The diagram below outlines the communication pathways between the Flask UI dashboard, the Python test runners, and the compiled C++ target emulator process.

```
          ┌───────────────────────────────────────────────┐
          │             Flask Web Dashboard               │
          │   (SSE Logs, Telemetry charts, Control API)   │
          └───────────────▲─────────────────┬─────────────┘
                          │                 │
                          │ Telemetry/Logs  │ Failures / Reboot
                          │                 ▼
 ┌────────────────────────────────────────────────────────┐
 │              Python Automation Framework               │
 │ - DeviceClient (Socket Console, Paramiko SSH Fallback) │
 │ - LogParser (Regex Diagnostics for Segfault/OOM)       │
 │ - ML Engine (TF-IDF + IsolationForest Outliers)        │
 │ - SQLite DB History & Base64 Report Generator          │
 └───────────────▲─────────────────┬──────────────────────┘
                 │                 │
                 │ Console stream  │ Commands (TCP Socket)
                 │                 ▼
 ┌────────────────────────────────────────────────────────┐
 │            C++ Device Emulator (Target)                │
 │ - Telemetry Loop Thread (CPU, Memory, Temp, Voltage)   │
 │ - CLI Command Server (status, reboot, inject_failure)  │
 │ - Failure Simulation (OOM Crash, Segfault, Delays)     │
 └────────────────────────────────────────────────────────┘
```

---

## 🌟 Key Features

1. **Multithreaded C++ Emulator**: Simulates device boot states (`BOOTLOADER`, `KERNEL_INIT`, `SERVICES_START`, `READY`) and spawns a background telemetry generator monitoring vitals (CPU load, voltage, temperatures). It runs a TCP console server, replicating a physical UART interface.
2. **Robust Python Test Client**: Connects via socket consoles to command the target and executes remote Unix commands via SSH using `paramiko` (with a local subprocess shell execution fallback for offline developer desktops).
3. **Advanced Log Diagnostics**: Uses regex signature parsers (`diagnostics/log_parser.py`) to detect segmentation faults (SIGSEGV), kernel panics, and systemd Out-of-Memory (OOM) killer events.
4. **ML Anomaly Classification**: Trains a scikit-learn `IsolationForest` model on vectorized log words (`TfidfVectorizer`). Computes decision scores in real-time, tagging abnormal system behaviors and logging anomaly counts.
5. **Standalone CSS HTML Reports**: Compiles execution history into HTML reports featuring base64-encoded, dark-themed decision score profiles generated via `matplotlib`.
6. **SQLite History Database**: Stores test run metrics (durations, average CPU/memory usage, maximum temperatures, pass/fail results) for trend analysis.
7. **Responsive UI Dashboard**: Built in Flask, using modern dark-mode glassmorphic styling, real-time Chart.js telemetry plots, pipeline history inspector modals, and Server-Sent Events (SSE) log streams.

---

## 📁 Repository Structure

```
├── .github/workflows/
│   └── ci.yml             # GitHub Actions CI pipeline (builds C++, trains ML, runs tests)
├── automation/
│   ├── logger.py          # Structured JSON and colored terminal logging
│   ├── device_client.py   # Connection sockets, SSH controllers, background log capture
│   └── test_runner.py     # Decorators, execution timing, and test retry routines
├── embedded_app/
│   ├── CMakeLists.txt     # Multi-platform CMake file for cross-compiling
│   ├── main.cpp           # Emulator lifecycle and OS signals coordinator
│   ├── simulator.cpp      # Telemetry streams and failure injection
│   └── socket_server.cpp  # TCP CLI and log broadcasting server
├── diagnostics/
│   ├── system_monitor.py  # psutil tracker checking memory growth and thread count
│   └── log_parser.py      # Regex parsers for segfaults, OOM-killers, and telemetry stats
├── ml_engine/
│   ├── trainer.py         # Baseline dataset generator and model trainer
│   └── anomaly_detector.py# Isolation Forest log scanner and matplotlib profile plotter
├── reports/
│   ├── history_db.py      # SQLite table schema mapping results and aggregates
│   └── report_generator.py# Self-contained HTML report compiler (embedded base64 charts)
├── tests/
│   ├── conftest.py        # Automatic emulator startup, telemetry threads, and DB hooks
│   ├── test_boot.py       # Validates boot phases and duration limits
│   ├── test_sensor.py     # Tests telemetry boundaries and sensor timeouts
│   ├── test_network.py    # Checks behavior under network delay injections
│   ├── test_memory.py     # Captures memory footprint leaks (RSS mb/s)
│   └── test_stress.py     # Confirms host/target resource bounds
├── configs/
│   └── config.json        # Global validation thresholds, connection ports, and model paths
├── dashboard/
│   ├── templates/
│   │   └── index.html     # Dark mode glassmorphic control console
│   └── app.py             # Flask dashboard web server and SSE log stream
├── scripts/
│   ├── build.sh           # Linux compilation script
│   ├── build.bat          # Windows compilation script
│   └── run_all.py         # One-click execution runner
├── requirements.txt       # Python packages list
└── README.md              # Technical framework documentation
```

---

## 🚀 Getting Started

### Prerequisites

- **Python**: Version `3.11`
- **Compiler**: GCC/G++ supporting C++17 (MinGW for Windows, standard build-essential for Linux)
- **CMake**: Version `3.10` or higher

### 1. Installation

Clone this repository and install Python package requirements:
```bash
pip install -r requirements.txt
```

### 2. Compile the C++ Target Emulator

Build the C++ emulator executable using the target platform build script:

- **Windows (CMD/PowerShell)**:
  ```cmd
  scripts\build.bat
  ```

- **Linux (Terminal)**:
  ```bash
  chmod +x scripts/build.sh
  ./scripts/build.sh
  ```

This places the compiled `device_emulator` binary in the project root.

### 3. Run the Automated Validation Suite

Execute the one-click master script to compile the emulator, train the ML weights, trigger the PyTest suite, collect stats, and export HTML reports:
```bash
python scripts/run_all.py
```

### 4. Launch the Telemetry Dashboard

Start the Flask dashboard to inspect test results and manually command the emulator:
```bash
python dashboard/app.py
```
Open your browser and navigate to `http://127.0.0.1:5000`.

---

## 🛠️ Validation Engineering Interview Alignment & Keywords

This project is tailored to validate critical domain expertise sought during validation engineer interviews:

- **Hardware-in-the-Loop (HIL) Simulation**: Validates target systems using mock serial interfaces and TCP control ports, similar to testing standard hardware reference designs.
- **Embedded Linux Kernel Exception Handling**: Simulates Out-Of-Memory (OOM) killer terminations and Segmentation Fault (SIGSEGV) exceptions, testing regression script robustness.
- **Log Diagnostic Extraction**: Demonstrates regex-based trace searches of kernel console buffers (`dmesg` / `journalctl` simulations).
- **Memory Footprint Validation**: Performs real-time memory leak checks, calculating target process Resident Set Size (RSS) growth metrics in Megabytes per second (MB/s).
- **ML Anomaly Classification**: Integrates `scikit-learn` outlier classifiers directly inside functional tests to automate anomaly score detection without relying on static thresholds.
- **CI/CD Integration**: Outlines containerized GitHub Actions workflows to build target binaries, execute Python validation frameworks, and archive HTML reports.
