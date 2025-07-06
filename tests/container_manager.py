import subprocess
import time
import logging
from pathlib import Path

class ContainerManager:
    def __init__(self, compose_file: Path):
        self.compose_file = compose_file
        self.container_name = "mcp-server"
        
    def __enter__(self):
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
    
    def start(self):
        """Build and start container"""
        logging.info("🚀 Starting E2E container environment...")
        
        try:
            # Build and run in detached mode
            subprocess.run(
                ["docker-compose", "-f", str(self.compose_file), "up", "-d", "--build"],
                check=True,
                capture_output=True,
                text=True
            )
            logging.info("Container started successfully.")
            self._wait_for_container_ready()
        except subprocess.CalledProcessError as e:
            logging.error(f"Error starting container: {e.stderr}")
            raise

    def _wait_for_container_ready(self, timeout=120, interval=5):
        logging.info(f"Waiting for container '{self.container_name}' to be ready...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Check if the container is running and healthy
                result = subprocess.run(
                    ["docker-compose", "-f", str(self.compose_file), "ps", "-q", self.container_name],
                    check=True,
                    capture_output=True,
                    text=True
                )
                container_id = result.stdout.strip()
                if container_id:
                    health_status = subprocess.run(
                        ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_id],
                        check=True,
                        capture_output=True,
                        text=True
                    ).stdout.strip()
                    if health_status == "healthy":
                        logging.info(f"Container '{self.container_name}' is healthy.")
                        return
                    elif health_status == "unhealthy":
                        logging.error(f"Container '{self.container_name}' is unhealthy.")
                        raise RuntimeError(f"Container '{self.container_name}' is unhealthy.")
                logging.info(f"Container '{self.container_name}' not yet healthy. Retrying in {interval} seconds...")
            except subprocess.CalledProcessError as e:
                logging.warning(f"Could not check container status: {e.stderr}")
            except Exception as e:
                logging.warning(f"An unexpected error occurred while waiting for container: {e}")
            time.sleep(interval)
        raise TimeoutError(f"Container '{self.container_name}' did not become healthy within {timeout} seconds.")

    def cleanup(self):
        """Stop and remove container"""
        logging.info("🧹 Cleaning up E2E container environment...")
        try:
            subprocess.run(
                ["docker-compose", "-f", str(self.compose_file), "down", "-v"],
                check=True,
                capture_output=True,
                text=True
            )
            logging.info("Container environment cleaned up.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error cleaning up container: {e.stderr}")
            raise

    def get_container_ip(self):
        """Get the IP address of the running container."""
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{ .NetworkSettings.IPAddress }}", self.container_name],
                check=True,
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logging.error(f"Error getting container IP: {e.stderr}")
            raise

