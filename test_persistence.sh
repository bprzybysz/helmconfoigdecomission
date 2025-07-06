#!/bin/bash

# This script tests the is_persistent_storage logic from file_system_mcp_server.py
# It's intended to be run manually or within a Docker container to verify paths.

if [ -z "$1" ]; then
    read -p "Enter a path to check for persistence (e.g., /mnt/data or /home/user): " input_path
elif [ -d "$1" ] || [ -f "$1" ]; then
    input_path="$1"
else
    echo "Error: Path '$1' does not exist or is not a valid file/directory." >&2
    exit 1
fi

if [[ "$input_path" == /mnt/* || "$input_path" == /persistence* ]]; then
    echo "Path '$input_path' is considered PERSISTENT storage."
else
    echo "Path '$input_path' is considered LOCAL storage."
fi
