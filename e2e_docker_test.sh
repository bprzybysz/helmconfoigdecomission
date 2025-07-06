#!/bin/bash

set -e # Exit immediately if a command exits with a non-zero status.

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}--- Starting E2E Docker Test ---
${NC}"

# --- Step 1: Build Docker images ---
echo -e "${GREEN}Building Docker images...${NC}"
podman-compose build
if [ $? -ne 0 ]; then
    echo -e "${RED}Docker build failed!${NC}"
    exit 1
fi
echo -e "${GREEN}Docker images built successfully.${NC}"

# --- Step 2: Run Docker containers in detached mode ---
echo -e "${GREEN}Starting Docker containers...${NC}"
podman-compose up -d
if [ $? -ne 0 ]; then
    echo -e "${RED}Docker containers failed to start!${NC}"
    podman-compose down # Clean up if failed to start
    exit 1
fi
echo -e "${GREEN}Docker containers started successfully.${NC}"

# Give the server a moment to start up
echo -e "${GREEN}Waiting for MCP server to be ready...${NC}"
sleep 5

# --- Step 3: Functional Test (Interact with MCP server) ---
# Create a temporary directory on the host to simulate persistent storage
TEST_DIR=$(mktemp -d -t mcp-test-XXXXXXXXXX)
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to create temporary directory.${NC}"
    podman-compose down
    exit 1
fi

# Ensure cleanup on exit
trap "echo -e \"${GREEN}Cleaning up temporary directory: ${TEST_DIR}${NC}\"; rm -rf ${TEST_DIR}; podman-compose down" EXIT

echo -e "${GREEN}Created temporary test directory: ${TEST_DIR}${NC}"

# Create a dummy file inside the simulated persistent storage
echo "test content" > "${TEST_DIR}/persistent_file.txt"

# Get the container ID of the mcp-server service
CONTAINER_ID=$(podman-compose ps -q mcp-server)

if [ -z "$CONTAINER_ID" ]; then
    echo -e "${RED}Could not find mcp-server container ID.${NC}"
    exit 1
fi

# Copy the temporary directory into the container at /mnt/test_data
# This simulates a mounted persistent volume for testing
docker cp "${TEST_DIR}" "${CONTAINER_ID}:/mnt/test_data"
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to copy test data to container.${NC}"
    exit 1
fi

# Now, run the test_persistence.sh script inside the container
# and then try to call the scan_files tool via a Python script
# Note: Direct MCP tool invocation from shell is complex. We'll simulate it
# by running a Python script inside the container that calls the tool.

echo -e "${GREEN}Running persistence check inside container...${NC}"
podman-compose exec mcp-server /app/test_persistence.sh <<EOF
/mnt/test_data/$(basename ${TEST_DIR})/persistent_file.txt
EOF

if [ $? -ne 0 ]; then
    echo -e "${RED}Persistence check inside container failed!${NC}"
    exit 1
fi

# --- Simulate MCP tool call for scan_files --- 
# For a real MCP interaction, you'd use an MCP client.
# Here, we'll run a Python script inside the container to call the function directly.

echo -e "${GREEN}Simulating scan_files MCP tool call inside container...${NC}"
# This Python script will call the scan_files function directly and print JSON output
SCAN_OUTPUT=$(podman-compose exec mcp-server python -c \
"from file_system_mcp_server import FileSystemMCPServer; \
server = FileSystemMCPServer(); \
results = list(server.scan_and_process_files('/mnt/test_data/$(basename ${TEST_DIR})', filetypes_filter=['.txt'], scan_and_delete=True)); \
import json; print(json.dumps(results))" 2>&1)

if [ $? -ne 0 ]; then
    echo -e "${RED}Simulated scan_files call failed!\nOutput:\n${SCAN_OUTPUT}${NC}"
    exit 1
fi

# Parse the JSON output and verify the results
# We expect the file not to be deleted and an error message indicating persistent storage protection

# Extract relevant fields using Python's json module for robust parsing
IS_DELETED=$(echo "$SCAN_OUTPUT" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data[0]['deleted'])")
ERROR_MESSAGE=$(echo "$SCAN_OUTPUT" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data[0].get('error', ''))")

if [ "$IS_DELETED" = "False" ] && [[ "$ERROR_MESSAGE" == *"persistent storage"* ]]; then
    echo -e "${GREEN}Functional test PASSED: Persistent file was NOT deleted as expected and error message is correct.${NC}"
else
    echo -e "${RED}Functional test FAILED: Unexpected scan_files result.\nIS_DELETED: ${IS_DELETED}\nERROR_MESSAGE: ${ERROR_MESSAGE}${NC}"
    exit 1
fi

# Verify the file was NOT deleted (from host's perspective, as a final check)
if [ -f "${TEST_DIR}/persistent_file.txt" ]; then
    echo -e "${GREEN}Host-side verification PASSED: Persistent file still exists on host.${NC}"
else
    echo -e "${RED}Host-side verification FAILED: Persistent file was deleted unexpectedly from host!${NC}"
    exit 1
fi

echo -e "${GREEN}--- E2E Docker Test Completed Successfully! ---\n${NC}"
