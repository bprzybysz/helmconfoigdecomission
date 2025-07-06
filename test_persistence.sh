#!/bin/bash

# This script tests the is_persistent_storage logic from file_system_mcp_server.py
# It's intended to be run manually or within a Docker container to verify paths.

read -p "Enter a path to check for persistence (e.g., /mnt/data or /home/user): " input_path

if [[ "$input_path" == /mnt/* || "$input_path" == /persistence* ]]; then
    echo "Path '$input_path' is considered PERSISTENT storage."
else
    echo "Path '$input_path' is considered LOCAL storage."
fi
