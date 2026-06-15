#include "simulator.hpp"
#include "socket_server.hpp"
#include <iostream>
#include <chrono>
#include <sstream>
#include <iomanip>
#include <random>
#include <cstdlib>
#include <cstring>

DeviceSimulator::DeviceSimulator(const std::string& log_filepath)
    : running_(false),
      boot_stage_(BootStage::BOOTLOADER),
      cpu_load_(5.0),
      mem_usage_(25.0),
      temperature_(35.0),
      voltage_(1.2),
      failure_memory_leak_(false),
      failure_sensor_timeout_(false),
      failure_network_delay_(false),
      active_failure_("none"),
      log_file_(log_filepath) {
    log_stream_.open(log_file_, std::ios::out | std::ios::app);
}

void DeviceSimulator::set_socket_server(SocketServer* server) {
    socket_server_ = server;
}

DeviceSimulator::~DeviceSimulator() {
    stop();
    if (log_stream_.is_open()) {
        log_stream_.close();
    }
    for (char* buf : leak_buffers_) {
        delete[] buf;
    }
    leak_buffers_.clear();
}

void DeviceSimulator::start() {
    if (running_) return;
    running_ = true;
    
    // Start boot thread
    int boot_id = ++current_boot_id_;
    boot_thread_ = std::thread(&DeviceSimulator::run_boot_sequence, this, boot_id);
    
    // Start telemetry monitoring thread
    telemetry_thread_ = std::thread(&DeviceSimulator::telemetry_loop, this);
}

void DeviceSimulator::stop() {
    if (!running_) return;
    running_ = false;

    if (boot_thread_.joinable()) {
        boot_thread_.join();
    }
    if (telemetry_thread_.joinable()) {
        telemetry_thread_.join();
    }
}

void DeviceSimulator::reset() {
    failure_memory_leak_ = false;
    failure_sensor_timeout_ = false;
    failure_network_delay_ = false;
    active_failure_ = "none";
    boot_stage_ = BootStage::BOOTLOADER;
    cpu_load_ = 5.0;
    mem_usage_ = 25.0;
    temperature_ = 35.0;
    voltage_ = 1.2;
    log_write("INFO", "System reset/reboot command received.");
}

void DeviceSimulator::trigger_reboot() {
    reset();
    int boot_id = ++current_boot_id_;
    if (boot_thread_.joinable()) {
        boot_thread_.detach();
    }
    boot_thread_ = std::thread(&DeviceSimulator::run_boot_sequence, this, boot_id);
}

void DeviceSimulator::inject_failure(const std::string& failure_type) {
    if (failure_type == "MEMORY_LEAK") {
        failure_memory_leak_ = true;
        active_failure_ = "MEMORY_LEAK";
        log_write("WARN", "Failure injected: MEMORY_LEAK. Target system memory consumption will rise.");
    } else if (failure_type == "SENSOR_TIMEOUT") {
        failure_sensor_timeout_ = true;
        active_failure_ = "SENSOR_TIMEOUT";
        log_write("ERROR", "Failure injected: SENSOR_TIMEOUT. Primary sensor communication interrupted.");
    } else if (failure_type == "NETWORK_DELAY") {
        failure_network_delay_ = true;
        active_failure_ = "NETWORK_DELAY";
        log_write("WARN", "Failure injected: NETWORK_DELAY. Virtual interfaces report high latency.");
    } else if (failure_type == "SEGFAULT") {
        log_write("CRITICAL", "Failure injected: SEGFAULT. Simulating memory access violation.");
        log_write("CRITICAL", "SEGMENTATION_FAULT: Invalid read/write at address 0x0000000C (Signal 11)");
        std::cout << "[CRITICAL] SEGMENTATION_FAULT: Invalid read/write at address 0x0000000C (Signal 11)" << std::endl;
        std::exit(139);
    } else {
        log_write("WARN", "Received unknown failure injection request: " + failure_type);
    }
}

std::string DeviceSimulator::get_status_json() {
    std::stringstream ss;
    ss << "{"
       << "\"boot_stage\":\"" << boot_stage_to_string(boot_stage_) << "\","
       << "\"cpu_load\":" << cpu_load_.load() << ","
       << "\"mem_usage\":" << mem_usage_.load() << ","
       << "\"temperature\":" << temperature_.load() << ","
       << "\"voltage\":" << voltage_.load() << ","
       << "\"active_failure\":\"" << active_failure_ << "\""
       << "}";
    return ss.str();
}

BootStage DeviceSimulator::get_boot_stage() const {
    return boot_stage_.load();
}

void DeviceSimulator::run_boot_sequence(int boot_id) {
    if (boot_id != current_boot_id_) return;
    boot_stage_ = BootStage::BOOTLOADER;
    
    // Stage 1: Bootloader
    log_write("INFO", "Device boot sequence initiated.");
    log_write("INFO", "Bootloader version 2026.06.15-g10a5e89b9 loading...");
    std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    if (boot_id != current_boot_id_ || !running_) return;

    // Stage 2: Kernel Init
    boot_stage_ = BootStage::KERNEL_INIT;
    log_write("INFO", "Linux version 6.1.0-21-amd64 (GCC version 12.2.0) bootstraping...");
    log_write("INFO", "Initializing RAM config: 512MB LPDDR4 detected.");
    log_write("INFO", "dmesg: [0.000000] Booting CPU 0x00 [hardware id 0x0]");
    std::this_thread::sleep_for(std::chrono::milliseconds(1500));
    if (boot_id != current_boot_id_ || !running_) return;

    // Stage 3: Services Start
    boot_stage_ = BootStage::SERVICES_START;
    log_write("INFO", "Starting systemd init system (v252.22)...");
    log_write("INFO", "Starting networking service: dhcpd...");
    log_write("INFO", "Starting telemetry daemon: pulse-ops-agent...");
    std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    if (boot_id != current_boot_id_ || !running_) return;

    // Stage 4: Ready
    boot_stage_ = BootStage::READY;
    log_write("INFO", "Device boot successful. System enters READY state.");
}

void DeviceSimulator::telemetry_loop() {
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<> cpu_dist(20.0, 35.0);
    std::uniform_real_distribution<> mem_dist(24.0, 28.0);
    std::uniform_real_distribution<> temp_dist(36.0, 42.0);
    std::uniform_real_distribution<> volt_dist(1.19, 1.21);

    while (running_) {
        // Only output telemetry once we are booted or running
        if (boot_stage_ == BootStage::READY) {
            double current_cpu = cpu_dist(gen);
            double current_mem = mem_dist(gen);
            double current_temp = temp_dist(gen);
            double current_volt = volt_dist(gen);

            // Apply failure anomalies if active
            if (failure_memory_leak_) {
                // Keep incrementing memory consumption
                mem_usage_ = mem_usage_ + 6.5;
                try {
                    char* leak = new char[10 * 1024 * 1024];
                    std::memset(leak, 0, 10 * 1024 * 1024);
                    leak_buffers_.push_back(leak);
                } catch (const std::bad_alloc&) {
                }
                if (mem_usage_ >= 95.0) {
                    log_write("CRITICAL", "MEMORY_CORRUPTION: Heap overflow detected in telemetry process.");
                    log_write("CRITICAL", "KERNEL_OUT_OF_MEMORY: systemd-oomd triggered.");
                    std::cout << "[CRITICAL] KERNEL_OUT_OF_MEMORY: OOM-killer invoked." << std::endl;
                    failure_memory_leak_ = false; // Stop leak to stabilize memory, but do not exit!
                }
            } else {
                mem_usage_ = current_mem;
            }

            if (failure_sensor_timeout_) {
                current_temp = -999.0;
                log_write("ERROR", "SENSOR_TIMEOUT: I2C bus read failure. Expected sensor address 0x48 unresponsive.");
            }

            if (failure_network_delay_) {
                log_write("WARN", "NETWORK_DELAY: Virtual interface eth0 packet latency spiked (350ms).");
            }

            cpu_load_ = current_cpu;
            temperature_ = current_temp;
            voltage_ = current_volt;

            // Generate structured log string
            std::stringstream ss;
            ss << "Telemetry update -> TEMP_SENSOR=" << std::fixed << std::setprecision(2) << temperature_.load()
               << " CPU_LOAD=" << cpu_load_.load()
               << " MEM_USAGE=" << mem_usage_.load()
               << " VOLTAGE=" << voltage_.load();
            
            log_write("INFO", ss.str());
        }
        
        // Wait 1 second between updates
        std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    }
}

void DeviceSimulator::log_write(const std::string& level, const std::string& message) {
    std::lock_guard<std::mutex> lock(log_mutex_);
    
    // Get formatted current timestamp
    auto now = std::chrono::system_clock::now();
    auto in_time_t = std::chrono::system_clock::to_time_t(now);
    auto duration = now.time_since_epoch();
    auto millis = std::chrono::duration_cast<std::chrono::milliseconds>(duration).count() % 1000;

    std::stringstream timestamp;
    timestamp << std::put_time(std::localtime(&in_time_t), "%Y-%m-%d %H:%M:%S")
              << "." << std::setfill('0') << std::setw(3) << millis;

    std::string formatted_log = "[" + timestamp.str() + "] [" + level + "] " + message;
    
    // Output to stdout and runtime file
    std::cout << formatted_log << std::endl;
    if (log_stream_.is_open()) {
        log_stream_ << formatted_log << std::endl;
        log_stream_.flush();
    }
    
    // Broadcast to connected socket clients
    if (socket_server_ != nullptr) {
        socket_server_->broadcast_log(formatted_log);
    }
}

std::string DeviceSimulator::boot_stage_to_string(BootStage stage) const {
    switch (stage) {
        case BootStage::BOOTLOADER:     return "BOOTLOADER";
        case BootStage::KERNEL_INIT:    return "KERNEL_INIT";
        case BootStage::SERVICES_START: return "SERVICES_START";
        case BootStage::READY:          return "READY";
    }
    return "UNKNOWN";
}
