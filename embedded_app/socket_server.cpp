#include "socket_server.hpp"
#include "simulator.hpp"
#include <iostream>
#include <algorithm>
#include <cstring>

#ifndef _WIN32
    #include <signal.h>
#endif

// We want to link the simulator log output to the socket server
extern void register_log_broadcast(const std::string& log_line);

SocketServer::SocketServer(int port, DeviceSimulator* simulator)
    : port_(port), simulator_(simulator), running_(false), server_fd_(INVALID_SOCKET) {}

SocketServer::~SocketServer() {
    stop();
}

void SocketServer::setup_sockets() {
#ifdef _WIN32
    WSADATA wsaData;
    int result = WSAStartup(MAKEWORD(2, 2), &wsaData);
    if (result != 0) {
        std::cerr << "WSAStartup failed with error: " << result << std::endl;
    }
#else
    // Disable SIGPIPE to prevent crash when writing to a closed socket
    signal(SIGPIPE, SIG_IGN);
#endif
}

void SocketServer::cleanup_sockets() {
#ifdef _WIN32
    WSACleanup();
#endif
}

void SocketServer::start() {
    if (running_) return;
    running_ = true;
    setup_sockets();

    server_fd_ = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd_ == INVALID_SOCKET) {
        std::cerr << "Failed to create socket." << std::endl;
        return;
    }

    // Set reuse address
    int opt = 1;
#ifdef _WIN32
    setsockopt(server_fd_, SOL_SOCKET, SO_REUSEADDR, (const char*)&opt, sizeof(opt));
#else
    setsockopt(server_fd_, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
#endif

    sockaddr_in address;
    std::memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(port_);

    if (bind(server_fd_, (struct sockaddr*)&address, sizeof(address)) == SOCKET_ERROR) {
        std::cerr << "Bind failed on port " << port_ << std::endl;
        closesocket(server_fd_);
        server_fd_ = INVALID_SOCKET;
        return;
    }

    if (listen(server_fd_, 5) == SOCKET_ERROR) {
        std::cerr << "Listen failed." << std::endl;
        closesocket(server_fd_);
        server_fd_ = INVALID_SOCKET;
        return;
    }

    std::cout << "Socket console server listening on port " << port_ << std::endl;
    listen_thread_ = std::thread(&SocketServer::listen_loop, this);
}

void SocketServer::stop() {
    if (!running_) return;
    running_ = false;

    if (server_fd_ != INVALID_SOCKET) {
        closesocket(server_fd_);
        server_fd_ = INVALID_SOCKET;
    }

    {
        std::lock_guard<std::mutex> lock(clients_mutex_);
        for (SOCKET client_socket : client_sockets_) {
            closesocket(client_socket);
        }
        client_sockets_.clear();
    }

    if (listen_thread_.joinable()) {
        listen_thread_.join();
    }
    cleanup_sockets();
}

void SocketServer::broadcast_log(const std::string& log_line) {
    std::lock_guard<std::mutex> lock(clients_mutex_);
    std::string data = log_line + "\n";
    
    // We send to all connected clients and clean up any dead ones
    auto it = client_sockets_.begin();
    while (it != client_sockets_.end()) {
        int bytes_sent = send(*it, data.c_str(), static_cast<int>(data.length()), 0);
        if (bytes_sent == SOCKET_ERROR) {
            closesocket(*it);
            it = client_sockets_.erase(it);
        } else {
            ++it;
        }
    }
}

void SocketServer::listen_loop() {
    while (running_) {
        sockaddr_in client_addr;
        socklen_t client_len = sizeof(client_addr);
        SOCKET client_socket = accept(server_fd_, (struct sockaddr*)&client_addr, &client_len);

        if (client_socket == INVALID_SOCKET) {
            if (running_) {
                std::cerr << "Accept failed." << std::endl;
            }
            break;
        }

        {
            std::lock_guard<std::mutex> lock(clients_mutex_);
            client_sockets_.push_back(client_socket);
        }

        std::cout << "Client connected to socket console." << std::endl;
        // Start a thread to handle client commands
        std::thread(&SocketServer::client_loop, this, client_socket).detach();
    }
}

void SocketServer::client_loop(SOCKET client_socket) {
    char buffer[1024];
    std::string command_buffer = "";

    while (running_) {
        std::memset(buffer, 0, sizeof(buffer));
        int bytes_received = recv(client_socket, buffer, sizeof(buffer) - 1, 0);

        if (bytes_received <= 0) {
            // Client disconnected or error
            break;
        }

        command_buffer += std::string(buffer, bytes_received);

        // Process line-by-line commands
        size_t newline_pos;
        while ((newline_pos = command_buffer.find('\n')) != std::string::npos) {
            std::string line = command_buffer.substr(0, newline_pos);
            command_buffer.erase(0, newline_pos + 1);

            // Strip carriage return if present
            if (!line.empty() && line.back() == '\r') {
                line.pop_back();
            }

            if (line.empty()) continue;

            std::cout << "Received socket command: " << line << std::endl;
            
            std::string response = "";
            if (line == "status") {
                response = simulator_->get_status_json() + "\n";
            } else if (line == "reboot") {
                simulator_->trigger_reboot();
                response = "OK\n";
            } else if (line.rfind("inject_failure ", 0) == 0) {
                std::string failure_type = line.substr(15);
                simulator_->inject_failure(failure_type);
                response = "OK\n";
            } else {
                response = "ERROR: Unknown command: " + line + "\n";
            }

            send(client_socket, response.c_str(), static_cast<int>(response.length()), 0);
        }
    }

    // Client cleanup
    {
        std::lock_guard<std::mutex> lock(clients_mutex_);
        auto it = std::find(client_sockets_.begin(), client_sockets_.end(), client_socket);
        if (it != client_sockets_.end()) {
            closesocket(client_socket);
            client_sockets_.erase(it);
        }
    }
    std::cout << "Client disconnected from socket console." << std::endl;
}
