import sys
import socket
import threading
import time
import json
import random
import os
from datetime import datetime

class PythonDeviceSimulator:
    """Mock target simulator in Python. Matches C++ emulator capabilities exactly."""
    def __init__(self, port=50007, log_filepath="device_runtime.log"):
        self.port = port
        self.log_filepath = log_filepath
        self.running = False
        
        # Vitals state
        self.boot_stage = "BOOTLOADER"
        self.cpu_load = 5.0
        self.mem_usage = 25.0
        self.temperature = 35.0
        self.voltage = 1.2

        # Failure states
        self.failure_memory_leak = False
        self.failure_sensor_timeout = False
        self.failure_network_delay = False
        self.active_failure = "none"

        self.server_sock = None
        self.client_socks = []
        self.clients_lock = threading.Lock()
        
        # Create log stream
        self.log_stream = open(self.log_filepath, "a", encoding="utf-8")

    def log_write(self, level: str, message: str):
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S") + f".{now.microsecond//1000:03d}"
        formatted = f"[{timestamp}] [{level}] {message}"
        
        # Console output
        print(formatted, flush=True)
        
        # File output
        self.log_stream.write(formatted + "\n")
        self.log_stream.flush()

        # Socket broadcast
        with self.clients_lock:
            dead_socks = []
            for sock in self.client_socks:
                try:
                    sock.sendall((formatted + "\n").encode("utf-8"))
                except socket.error:
                    dead_socks.append(sock)
            for sock in dead_socks:
                try:
                    sock.close()
                except Exception:
                    pass
                self.client_socks.remove(sock)

    def trigger_reboot(self):
        self.failure_memory_leak = False
        self.failure_sensor_timeout = False
        self.failure_network_delay = False
        self.active_failure = "none"
        self.boot_stage = "BOOTLOADER"
        self.cpu_load = 5.0
        self.mem_usage = 25.0
        self.temperature = 35.0
        self.voltage = 1.2
        self.log_write("INFO", "System reset/reboot command received.")
        
        # Restart boot thread
        threading.Thread(target=self._run_boot_sequence, daemon=True).start()

    def inject_failure(self, failure_type: str):
        if failure_type == "MEMORY_LEAK":
            self.failure_memory_leak = True
            self.active_failure = "MEMORY_LEAK"
            self.log_write("WARN", "Failure injected: MEMORY_LEAK. Target system memory consumption will rise.")
        elif failure_type == "SENSOR_TIMEOUT":
            self.failure_sensor_timeout = True
            self.active_failure = "SENSOR_TIMEOUT"
            self.log_write("ERROR", "Failure injected: SENSOR_TIMEOUT. Primary sensor communication interrupted.")
        elif failure_type == "NETWORK_DELAY":
            self.failure_network_delay = True
            self.active_failure = "NETWORK_DELAY"
            self.log_write("WARN", "Failure injected: NETWORK_DELAY. Virtual interfaces report high latency.")
        elif failure_type == "SEGFAULT":
            self.log_write("CRITICAL", "Failure injected: SEGFAULT. Simulating memory access violation.")
            self.log_write("CRITICAL", "SEGMENTATION_FAULT: Invalid read/write at address 0x0000000C (Signal 11)")
            print("[CRITICAL] SEGMENTATION_FAULT: Invalid read/write at address 0x0000000C (Signal 11)", flush=True)
            os._exit(139)
        else:
            self.log_write("WARN", f"Received unknown failure injection request: {failure_type}")

    def get_status_json(self) -> str:
        return json.dumps({
            "boot_stage": self.boot_stage,
            "cpu_load": round(self.cpu_load, 2),
            "mem_usage": round(self.mem_usage, 2),
            "temperature": round(self.temperature, 2),
            "voltage": round(self.voltage, 2),
            "active_failure": self.active_failure
        })

    def _run_boot_sequence(self):
        # Stage 1: Bootloader
        self.log_write("INFO", "Device boot sequence initiated.")
        self.log_write("INFO", "Bootloader version 2026.06.15-g10a5e89b9 loading...")
        time.sleep(1.0)
        
        # Stage 2: Kernel Init
        self.boot_stage = "KERNEL_INIT"
        self.log_write("INFO", "Linux version 6.1.0-21-amd64 (GCC version 12.2.0) bootstraping...")
        self.log_write("INFO", "Initializing RAM config: 512MB LPDDR4 detected.")
        self.log_write("INFO", "dmesg: [0.000000] Booting CPU 0x00 [hardware id 0x0]")
        time.sleep(1.5)

        # Stage 3: Services Start
        self.boot_stage = "SERVICES_START"
        self.log_write("INFO", "Starting systemd init system (v252.22)...")
        self.log_write("INFO", "Starting networking service: dhcpd...")
        self.log_write("INFO", "Starting telemetry daemon: pulse-ops-agent...")
        time.sleep(1.0)

        # Stage 4: Ready
        self.boot_stage = "READY"
        self.log_write("INFO", "Device boot successful. System enters READY state.")

    def _telemetry_loop(self):
        while self.running:
            if self.boot_stage == "READY":
                current_cpu = random.uniform(20.0, 35.0)
                current_mem = random.uniform(24.0, 28.0)
                current_temp = random.uniform(36.0, 42.0)
                current_volt = random.uniform(1.19, 1.21)

                if self.failure_memory_leak:
                    self.mem_usage += 6.5
                    if self.mem_usage >= 95.0:
                        self.log_write("CRITICAL", "MEMORY_CORRUPTION: Heap overflow detected in telemetry process.")
                        self.log_write("CRITICAL", "KERNEL_OUT_OF_MEMORY: systemd-oomd triggered.")
                        print("[CRITICAL] KERNEL_OUT_OF_MEMORY: OOM-killer invoked.", flush=True)
                        os._exit(137)
                else:
                    self.mem_usage = current_mem

                if self.failure_sensor_timeout:
                    current_temp = -999.0
                    self.log_write("ERROR", "SENSOR_TIMEOUT: I2C bus read failure. Expected sensor address 0x48 unresponsive.")

                if self.failure_network_delay:
                    self.log_write("WARN", "NETWORK_DELAY: Virtual interface eth0 packet latency spiked (350ms).")

                self.cpu_load = current_cpu
                self.temperature = current_temp
                self.voltage = current_volt

                self.log_write("INFO", f"Telemetry update -> TEMP_SENSOR={self.temperature:.2f} CPU_LOAD={self.cpu_load:.2f} MEM_USAGE={self.mem_usage:.2f} VOLTAGE={self.voltage:.2f}")

            time.sleep(1.0)

    def _client_handler(self, sock):
        buffer = ""
        while self.running:
            try:
                data = sock.recv(1024)
                if not data:
                    break
                buffer += data.decode("utf-8", errors="ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    
                    response = ""
                    if line == "status":
                        response = self.get_status_json() + "\n"
                    elif line == "reboot":
                        self.trigger_reboot()
                        response = "OK\n"
                    elif line.startswith("inject_failure "):
                        failure_type = line[15:]
                        self.inject_failure(failure_type)
                        response = "OK\n"
                    else:
                        response = f"ERROR: Unknown command: {line}\n"
                    
                    sock.sendall(response.encode("utf-8"))
            except socket.error:
                break
        
        with self.clients_lock:
            if sock in self.client_socks:
                sock.close()
                self.client_socks.remove(sock)

    def _accept_loop(self):
        while self.running:
            try:
                sock, addr = self.server_sock.accept()
                with self.clients_lock:
                    self.client_socks.append(sock)
                threading.Thread(target=self._client_handler, args=(sock,), daemon=True).start()
            except socket.error:
                break

    def start(self):
        self.running = True
        
        # Setup Server socket
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(("127.0.0.1", self.port))
        self.server_sock.listen(5)
        
        # Threads
        threading.Thread(target=self._accept_loop, daemon=True).start()
        threading.Thread(target=self._run_boot_sequence, daemon=True).start()
        threading.Thread(target=self._telemetry_loop, daemon=True).start()
        
        self.log_write("INFO", f"Python Simulator Server listening on port {self.port}")
        
        # Loop to keep main thread alive
        try:
            while self.running:
                time.sleep(0.5)
        except (KeyboardInterrupt, SystemExit):
            self.stop()

    def stop(self):
        self.running = False
        if self.server_sock:
            self.server_sock.close()
        with self.clients_lock:
            for sock in self.client_socks:
                sock.close()
            self.client_socks.clear()
        self.log_stream.close()

if __name__ == "__main__":
    port = 50007
    log_file = "device_runtime.log"
    
    # Simple argv parsing
    args = sys.argv[1:]
    for idx, arg in enumerate(args):
        if arg == "--port" and idx + 1 < len(args):
            port = int(args[idx+1])
        elif arg == "--log" and idx + 1 < len(args):
            log_file = args[idx+1]
            
    sim = PythonDeviceSimulator(port=port, log_filepath=log_file)
    sim.start()
