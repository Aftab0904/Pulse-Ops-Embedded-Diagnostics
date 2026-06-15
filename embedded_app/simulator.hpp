#ifndef SIMULATOR_HPP
#define SIMULATOR_HPP

#include <string>
#include <thread>
#include <mutex>
#include <atomic>
#include <fstream>
#include <vector>

enum class BootStage {
    BOOTLOADER,
    KERNEL_INIT,
    SERVICES_START,
    READY
};

class SocketServer;

class DeviceSimulator {
public:
    DeviceSimulator(const std::string& log_filepath);
    ~DeviceSimulator();

    void start();
    void stop();
    void reset();

    void set_socket_server(SocketServer* server);

    // Command Actions
    void inject_failure(const std::string& failure_type);
    void trigger_reboot();
    std::string get_status_json();

    // Getter for checking state
    BootStage get_boot_stage() const;

private:
    void run_boot_sequence();
    void telemetry_loop();
    void log_write(const std::string& level, const std::string& message);

    std::string boot_stage_to_string(BootStage stage) const;

    SocketServer* socket_server_ = nullptr;
    std::atomic<bool> running_;
    std::atomic<BootStage> boot_stage_;
    std::atomic<double> cpu_load_;
    std::atomic<double> mem_usage_;
    std::atomic<double> temperature_;
    std::atomic<double> voltage_;
    
    // Injected failure variables
    std::atomic<bool> failure_memory_leak_;
    std::atomic<bool> failure_sensor_timeout_;
    std::atomic<bool> failure_network_delay_;
    std::string active_failure_;

    std::thread boot_thread_;
    std::thread telemetry_thread_;
    std::mutex log_mutex_;
    std::string log_file_;
    std::ofstream log_stream_;
    std::vector<char*> leak_buffers_;
};

#endif // SIMULATOR_HPP
