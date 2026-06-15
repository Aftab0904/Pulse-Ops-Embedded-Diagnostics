#include "simulator.hpp"
#include "socket_server.hpp"
#include <iostream>
#include <string>
#include <csignal>
#include <atomic>
#include <chrono>

std::atomic<bool> keep_running(true);

void signal_handler(int signal) {
    std::cout << "\nSignal " << signal << " received. Stopping emulator..." << std::endl;
    keep_running = false;
}

int main(int argc, char* argv[]) {
    // Register signal handlers
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    int port = 50007;
    std::string log_file = "device_runtime.log";

    // Simple argument parsing
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--port" && i + 1 < argc) {
            port = std::stoi(argv[++i]);
        } else if (arg == "--log" && i + 1 < argc) {
            log_file = argv[++i];
        } else if (arg == "--help" || arg == "-h") {
            std::cout << "Usage: device_emulator [options]\n"
                      << "Options:\n"
                      << "  --port <number>   TCP port for console server (default: 50007)\n"
                      << "  --log <path>      Path to simulated log file (default: device_runtime.log)\n"
                      << "  --help, -h        Show this help message\n";
            return 0;
        }
    }

    std::cout << "===========================================" << std::endl;
    std::cout << "Starting Pulse-Ops Embedded Linux Device Emulator" << std::endl;
    std::cout << "Port: " << port << std::endl;
    std::cout << "Log File: " << log_file << std::endl;
    std::cout << "===========================================" << std::endl;

    // Initialize simulator
    DeviceSimulator simulator(log_file);

    // Initialize socket server
    SocketServer server(port, &simulator);
    
    // Link them together
    simulator.set_socket_server(&server);

    // Start threads
    simulator.start();
    server.start();

    // Loop until signal received
    while (keep_running) {
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        // Check if simulator itself has exited due to critical failure (OOM / Segfault)
        // Wait, simulator exits the process on OOM/Segfault, so this loop will just end.
    }

    std::cout << "Stopping socket server..." << std::endl;
    server.stop();
    
    std::cout << "Stopping simulator..." << std::endl;
    simulator.stop();

    std::cout << "Emulator stopped successfully." << std::endl;
    return 0;
}
