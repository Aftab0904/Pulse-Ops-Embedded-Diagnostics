#ifndef SOCKET_SERVER_HPP
#define SOCKET_SERVER_HPP

#include <string>
#include <vector>
#include <thread>
#include <mutex>
#include <atomic>

// Cross-platform Socket wrapper
#ifdef _WIN32
    #include <winsock2.h>
    #include <ws2tcpip.h>
    typedef int socklen_t;
#else
    #include <sys/socket.h>
    #include <netinet/in.h>
    #include <unistd.h>
    #include <arpa/inet.h>
    typedef int SOCKET;
    #define INVALID_SOCKET -1
    #define SOCKET_ERROR -1
    #define closesocket(s) close(s)
#endif

class DeviceSimulator; // Forward declaration

class SocketServer {
public:
    SocketServer(int port, DeviceSimulator* simulator);
    ~SocketServer();

    void start();
    void stop();
    void broadcast_log(const std::string& log_line);

private:
    void listen_loop();
    void client_loop(SOCKET client_socket);
    void setup_sockets();
    void cleanup_sockets();

    int port_;
    DeviceSimulator* simulator_;
    std::atomic<bool> running_;
    SOCKET server_fd_;

    std::thread listen_thread_;
    std::vector<SOCKET> client_sockets_;
    std::mutex clients_mutex_;
};

#endif // SOCKET_SERVER_HPP
