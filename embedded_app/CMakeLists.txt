cmake_minimum_required(VERSION 3.10)
project(device_emulator CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Sources
set(SOURCES
    main.cpp
    simulator.cpp
    socket_server.cpp
)

# Headers
set(HEADERS
    simulator.hpp
    socket_server.hpp
)

add_executable(device_emulator ${SOURCES} ${HEADERS})

# Locate Threads
find_package(Threads REQUIRED)
target_link_libraries(device_emulator PRIVATE Threads::Threads)

# If compiling on Windows, link Winsock
if(WIN32)
    target_link_libraries(device_emulator PRIVATE ws2_32)
endif()
