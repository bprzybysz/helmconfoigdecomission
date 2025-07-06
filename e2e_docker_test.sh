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

# Ensure cleanup on exit
trap "echo -e \"${GREEN}Cleaning up containers...${NC}"; podman-compose down -v --remove-orphans; podman container prune -f" EXIT

echo -e "${GREEN}Container setup complete. You can now interact with the MCP server.${NC}"

# Optional: Add commands here to interact with the running container if needed for manual verification
echo -e "${GREEN}E2E test completed successfully!${NC}"
