import pytest
import subprocess
import time
import requests
import asyncio
import os
from fastmcp.client import Client

@pytest.fixture(scope="module")
def mcp_client():
    # Ensure a clean state before starting
    print("\nEnsuring clean state...")
    subprocess.run(["podman-compose", "down", "-v", "--remove-orphans"], capture_output=True)
    subprocess.run(["podman", "container", "prune", "-f"], capture_output=True)

    # Start podman-compose services
    print("Starting MCP server with podman-compose...")
    subprocess.run(["podman-compose", "up", "-d", "--build"], check=True)
    
    server_url = "http://localhost:5001"
    timeout = 60 # seconds
    start_time = time.time()

    # Get container ID for log-based readiness check
    # Get container ID for log-based readiness check
    # podman-compose names containers as <project_name>_<service_name>_<instance_number>
    # The project name is usually the directory name.
    project_name = os.path.basename(os.getcwd())
    container_name = f"{project_name}_mcp-server_1"
    container_id = subprocess.run(["podman", "ps", "-q", "--filter", f"name={container_name}"], capture_output=True, text=True, check=True).stdout.strip()
    if not container_id:
        raise RuntimeError("Could not get mcp-server container ID")

    # Wait for the MCP server to be ready by tailing logs
    print(f"Waiting for MCP server to be ready (tailing logs of {container_id})...")
    readiness_string = "Uvicorn running on http://0.0.0.0:5000"
    log_process = subprocess.Popen(["podman", "logs", "-f", container_id], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    ready = False
    for line in log_process.stdout:
        print(f"[MCP Log]: {line.strip()}") # Print logs for visibility
        if readiness_string in line:
            ready = True
            print("MCP server is ready (detected from logs)!")
            break
        if time.time() - start_time > timeout:
            log_process.terminate()
            raise RuntimeError("MCP server did not become ready in time (log check timeout)")
    
    if not ready:
        log_process.terminate()
        raise RuntimeError("MCP server did not become ready (readiness string not found)")

    # Terminate the log tailing process after readiness is confirmed
    log_process.terminate()

    # Initialize FastMCPClient
    client = Client(server_url)
    yield client

    # Teardown: Stop podman-compose services
    print("\nStopping MCP server with podman-compose...")
    subprocess.run(["podman-compose", "down", "-v", "--remove-orphans"], check=True)
    subprocess.run(["podman", "container", "prune", "-f"], check=True)

def test_mcp_scan_files(mcp_client):
    print("\nCalling scan_files tool...")
    # Assuming 'scan_files' is a registered tool in your MCP server
    # You might need to adjust the path based on your container's file system
    result = mcp_client.call_tool("scan_files", path="/app", filetypes_filter=[".py"])
    assert isinstance(result, list)
    assert len(result) > 0, "scan_files returned no results"
    print(f"scan_files returned {len(result)} files.")
    # You can add more assertions here to check the content of the results
