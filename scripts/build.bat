@echo off
echo ===========================================
echo Building C++ Embedded Device Emulator (Windows)
echo ===========================================

if not exist build mkdir build
cd build
cmake ../embedded_app
cmake --build . --config Release
cd ..

if exist build\Release\device_emulator.exe (
    copy build\Release\device_emulator.exe .
    echo ===========================================
    echo Build Successful: device_emulator.exe copied to root.
    echo ===========================================
) else if exist build\device_emulator.exe (
    copy build\device_emulator.exe .
    echo ===========================================
    echo Build Successful: device_emulator.exe copied to root.
    echo ===========================================
) else (
    echo.
    echo [WARNING] CMake build did not output device_emulator.exe.
    echo Attempting direct g++ compilation fallback...
    echo.
    g++ -std=c++17 embedded_app/main.cpp embedded_app/simulator.cpp embedded_app/socket_server.cpp -lws2_32 -pthread -o device_emulator.exe
    if exist device_emulator.exe (
        echo ===========================================
        echo Fallback Build Successful: device_emulator.exe compiled.
        echo ===========================================
    ) else (
        echo ===========================================
        echo [ERROR] Compilation failed. Ensure g++ MinGW or MSVC is in PATH.
        echo ===========================================
    )
)
