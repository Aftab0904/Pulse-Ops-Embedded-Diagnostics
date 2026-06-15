#!/bin/bash
echo "==========================================="
echo "Building C++ Embedded Device Emulator (Linux)"
echo "==========================================="

mkdir -p build
cd build
cmake ../embedded_app
make
cd ..

if [ -f build/device_emulator ]; then
    cp build/device_emulator .
    echo "==========================================="
    echo "Build Successful: device_emulator copied to root."
    echo "==========================================="
else
    echo ""
    echo "[WARNING] CMake build did not output device_emulator."
    echo "Attempting direct g++ compilation fallback..."
    echo ""
    g++ -std=c++17 embedded_app/main.cpp embedded_app/simulator.cpp embedded_app/socket_server.cpp -pthread -o device_emulator
    if [ -f device_emulator ]; then
        echo "==========================================="
        echo "Fallback Build Successful: device_emulator compiled."
        echo "==========================================="
    else
        echo "==========================================="
        echo "[ERROR] Compilation failed. Ensure g++ and make are installed."
        echo "==========================================="
    fi
fi
