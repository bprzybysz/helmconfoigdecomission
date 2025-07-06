#!/bin/bash

set -e

# Check if ENV is not 'prod' and run test_persistence.sh
if [ "$ENV" != "prod" ]; then
    echo "Running persistence test..."
    /app/test_persistence.sh /mnt/data/test_path
fi

# Execute the main MCP server application
exec python mcp_server_main.py
