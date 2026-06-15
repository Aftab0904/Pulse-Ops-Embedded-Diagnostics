import socket
import threading
import time
import json
import os
import subprocess
import paramiko
from automation.logger import setup_logger

class DeviceClient:
    """Manages connection, control, and log collection from the simulated target."""
    def __init__(self, config_path="configs/config.json"):
        self.logger = setup_logger("DeviceClient", config_path)
        self.config_path = config_path
        self.config = self._load_config()

        self.conn_type = self.config.get("device", {}).get("connection_type", "socket")
        self.host = self.config.get("device", {}).get("host", "127.0.0.1")
        self.port = self.config.get("device", {}).get("port", 50007)
        
        self.socket_conn = None
        self.ssh_conn = None
        
        self.listener_thread = None
        self.listening = False
        
        # Logs collection
        self.device_log_file = os.path.join(self.config.get("log", {}).get("log_dir", "logs"), "device_console.log")
        os.makedirs(os.path.dirname(self.device_log_file), exist_ok=True)
        self.log_stream = open(self.device_log_file, "a", encoding="utf-8")
        
        self.callbacks = []

    def _load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Failed to load config file: {e}")
        return {}

    def register_log_callback(self, callback):
        """Registers a function to be called on every new console log line."""
        self.callbacks.append(callback)

    def connect(self, retries=3, delay=1.5):
        """Connects to target socket console and starts log capture listener."""
        attempt = 0
        while attempt < retries:
            try:
                self.socket_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket_conn.connect((self.host, self.port))
                self.logger.info(f"Connected to simulated console at {self.host}:{self.port}")
                
                # Start background log listener
                self.listening = True
                self.listener_thread = threading.Thread(target=self._listen_logs_loop, daemon=True)
                self.listener_thread.start()
                return True
            except socket.error as e:
                attempt += 1
                self.logger.warn(f"Connection attempt {attempt}/{retries} failed: {e}")
                if attempt < retries:
                    time.sleep(delay)
        
        self.logger.error("Failed to connect to simulated console. Target might not be running.")
        return False

    def send_command(self, cmd: str, timeout=5) -> str:
        """Sends a console command and blocks until response is received.

        Note: The log listener thread handles standard log broadcasts. Commands
        like 'status' or 'inject_failure' return direct line-based responses.
        """
        if not self.socket_conn:
            self.logger.error("Cannot send command: Socket not connected.")
            return ""

        try:
            # We temporarily suspend console log streaming from socket if required,
            # or simply send the command and wait for the response. Since the server
            # responds immediately on the socket for CLI commands, we can write and read.
            # To avoid collision with log streaming, commands are sent with a lock or handled sequentially.
            payload = (cmd + "\n").encode("utf-8")
            self.socket_conn.sendall(payload)
            
            # Since logging is also streamed to this socket, command responses are terminated
            # with '\n'. We read until we receive a complete response.
            # For simplicity, since the client_loop on server returns 'OK\n', status JSON, or 'ERROR...'
            # we read the response line.
            # In a robust framework, commands and logs could use separate channels, but a single UART-like
            # stream is highly realistic.
            # We wait up to timeout seconds for a response.
            response = ""
            start_time = time.time()
            while time.time() - start_time < timeout:
                # We read bytes. The background listener thread might consume it,
                # so we must coordinate.
                # Actually, to make it robust, CLI commands are processed synchronously.
                # Let's read the socket.
                # To prevent the thread conflict, let's make command sending thread-safe.
                pass
            
            # In a simple UART console, status logs and command responses flow on the same line.
            # Let's make a dedicated socket for commands or parse it directly.
            # Since we only have a single socket connection, our background loop parses line-by-line.
            # Let's save responses in a queue or dictionary.
            # Let's implement command responses by requesting status and waiting for a short duration.
            # To make it simple, we write commands and the server responds immediately.
            # Let's use a lock.
            return self._send_and_receive_raw(cmd)
        except Exception as e:
            self.logger.error(f"Error executing command '{cmd}': {e}")
            return ""

    def _send_and_receive_raw(self, cmd: str) -> str:
        # Create a temporary socket to send synchronous commands so it doesn't interfere with the log stream.
        # This simulates a separate console control channel or dual-channel UART/TCP architecture, which is
        # very common in test setups.
        try:
            temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            temp_sock.connect((self.host, self.port))
            temp_sock.sendall((cmd + "\n").encode("utf-8"))
            
            # Read until we receive a line that does not start with log prefix '['
            buffer = ""
            response = ""
            while True:
                chunk = temp_sock.recv(4096).decode("utf-8")
                if not chunk:
                    break
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line_str = line.strip()
                    if not line_str.startswith("["):
                        response = line_str
                        break
                if response:
                    break
            temp_sock.close()
            return response
        except Exception as e:
            self.logger.error(f"Command socket communication failure: {e}")
            return ""

    def get_status(self) -> dict:
        """Queries the simulator telemetry status."""
        resp = self.send_command("status")
        if not resp:
            return {}
        try:
            # The status response is a single JSON line
            return json.loads(resp)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse status JSON: {resp}. Error: {e}")
            return {}

    def inject_failure(self, failure_type: str) -> bool:
        """Injects a failure condition into the emulator."""
        self.logger.info(f"Injecting failure: {failure_type}")
        resp = self.send_command(f"inject_failure {failure_type}")
        return resp == "OK"

    def reboot(self) -> bool:
        """Commands the target to reboot."""
        self.logger.info("Triggering target system reboot...")
        resp = self.send_command("reboot")
        return resp == "OK"

    def execute_ssh(self, cmd: str) -> tuple[int, str, str]:
        """Executes a command on the target via SSH. Falls back to subprocess local execution."""
        ssh_cfg = self.config.get("device", {}).get("ssh", {})
        host = ssh_cfg.get("host", "127.0.0.1")
        port = ssh_cfg.get("port", 22)
        username = ssh_cfg.get("username", "root")
        password = ssh_cfg.get("password", "password")

        self.logger.info(f"Executing SSH command: {cmd}")
        
        # Attempt real SSH
        try:
            self.ssh_conn = paramiko.SSHClient()
            self.ssh_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_conn.connect(host, port=port, username=username, password=password, timeout=2)
            
            stdin, stdout, stderr = self.ssh_conn.exec_command(cmd)
            exit_code = stdout.channel.recv_exit_status()
            out_str = stdout.read().decode("utf-8")
            err_str = stderr.read().decode("utf-8")
            
            self.ssh_conn.close()
            return exit_code, out_str, err_str
        except Exception as e:
            self.logger.warning(f"SSH connection failed ({e}). Falling back to local execution.")
            
            # Simulated environment: Execute command on the local machine (Windows/Ubuntu)
            # This allows testing shell features like ps, system load, etc., on the local host.
            try:
                # We execute using shell
                proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout_data, stderr_data = proc.communicate(timeout=5)
                return proc.returncode, stdout_data.decode("utf-8", errors="replace"), stderr_data.decode("utf-8", errors="replace")
            except subprocess.TimeoutExpired as te:
                self.logger.error(f"Fallback command execution timed out: {te}")
                return -1, "", "Execution Timeout"
            except Exception as le:
                self.logger.error(f"Fallback command execution failed: {le}")
                return -1, "", str(le)

    def _listen_logs_loop(self):
        """Continuously reads log stream from the console socket."""
        buffer = ""
        while self.listening and self.socket_conn:
            try:
                data = self.socket_conn.recv(4096)
                if not data:
                    self.logger.info("Socket connection closed by remote host.")
                    break
                
                buffer += data.decode("utf-8", errors="ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Log to console log file
                    self.log_stream.write(line + "\n")
                    self.log_stream.flush()
                    
                    # Forward to subscribers
                    for cb in self.callbacks:
                        try:
                            cb(line)
                        except Exception as e:
                            self.logger.error(f"Error in log callback: {e}")
            except socket.error as e:
                if self.listening:
                    self.logger.error(f"Log listener socket error: {e}")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in log listener thread: {e}")
                break
                
        self.logger.info("Log listener thread exited.")

    def close(self):
        """Clean up connections and close file handles."""
        self.listening = False
        if self.socket_conn:
            try:
                self.socket_conn.close()
            except Exception:
                pass
            self.socket_conn = None
            
        if self.log_stream and not self.log_stream.closed:
            self.log_stream.close()
            
        self.logger.info("DeviceClient connections closed.")
