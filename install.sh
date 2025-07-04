#!/bin/bash

# Detect the operating system
case "$(uname -s)" in
    Linux*)
        echo "Detected Linux"
        exec sudo bash "$(dirname "$0")/install_linux.sh"
        ;;
    Darwin*)
        echo "Detected macOS"
        exec sudo bash "$(dirname "$0")/install_macos.sh"
        ;;
    CYGWIN*|MINGW32*|MSYS*|MINGW*)
        echo "Detected Windows"
        echo "Please run install_windows.ps1 as Administrator"
        exit 1
        ;;
    *)
        echo "Unsupported operating system"
        exit 1
        ;;
esac
