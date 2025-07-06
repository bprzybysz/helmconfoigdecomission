#!/bin/bash

# Define colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Ensure a clean state before starting
echo -e "${GREEN}Ensuring clean state...${NC}"
podman-compose down -v --remove-orphans 2>/dev/null || true
podman container prune -f 2>/dev/null || true

set -e # Exit immediately if a command exits with a non-zero status.

# --- Step 1: Build Docker images ---
echo -e "${GREEN}Building Docker images...${NC}"
podman-compose build
if [ $? -ne 0 ]; then
    echo -e "${RED}Docker images failed to build!${NC}"
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

# Cleanup function
cleanup() {
    echo -e "${GREEN}Cleaning up containers...${NC}"
    podman-compose down -v --remove-orphans
    podman container prune -f
}

# Ensure cleanup on exit
trap cleanup EXIT

echo -e "${GREEN}Container setup complete. You can now interact with the MCP server.${NC}"

# Give the MCP server some time to start up
echo -e "${GREEN}Waiting for MCP server to start (10 seconds)...${NC}"
sleep 10

# Get the MCP server container ID
CONTAINER_ID=$(podman ps -aqf "name=helmconfoigdecomission_mcp-server_1")

if [ -z "$CONTAINER_ID" ]; then
    echo -e "${RED}Error: MCP server container ID not found!${NC}"
    exit 1
fi

echo -e "${GREEN}MCP Server Container ID: ${CONTAINER_ID}${NC}"

# Check if container is running
if [ "$(podman inspect -f '{{.State.Running}}' "$CONTAINER_ID")" != "true" ]; then
    echo -e "${RED}Error: MCP server container is not running!${NC}"
    exit 1
fi

# Run a test command inside the container
echo -e "${GREEN}Running a test command inside the container (ls -l /app)...${NC}"
podman exec "$CONTAINER_ID" ls -l /app

if [ $? -ne 0 ]; then
    echo -e "${RED}Test command inside container failed!${NC}"
    exit 1
fi

echo -e "${GREEN}Test command inside container succeeded.${NC}"

# Clone cloudnative-pg repository inside the container
REPO_DIR="/app/cloudnative-pg"

echo -e "${GREEN}Cloning cloudnative-pg/cloudnative-pg into ${REPO_DIR} inside the container...${NC}"
podman exec "$CONTAINER_ID" git clone https://github.com/cloudnative-pg/cloudnative-pg.git "$REPO_DIR"

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to clone cloudnative-pg repository!${NC}"
    exit 1
fi

echo -e "${GREEN}Repository cloned successfully.${NC}"

echo -e "${GREEN}E2E test completed successfully!${NC}"
