# tests/container_manager.py
import asyncio
import subprocess
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

class AsyncContainerManager:
    """Non-blocking async container lifecycle management."""
    
    def __init__(
        self, 
        compose_file: Path, 
        service_name: str = "mcp-server",
        startup_timeout: int = 60,
        command_timeout: int = 30
    ):
        self.compose_file = compose_file
        self.service_name = service_name
        self.container_name = f"helmconfoigdecomission_{service_name}_1"
        self._is_running = False
        self.startup_timeout = startup_timeout
        self.command_timeout = command_timeout

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def start(self) -> None:
        """Build and start containers with timeout protection."""
        logger.info("🚀 Starting container environment...")
        try:
            # ✅ Add timeout to container startup
            process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "podman-compose", "-f", str(self.compose_file),
                    "up", "--build", "-d",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=self.startup_timeout
            )
            
            # ✅ Add timeout to communicate
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30
            )
            
            if process.returncode != 0:
                raise RuntimeError(f"Container startup failed: {stderr.decode()}")
                
            # ✅ Add timeout to readiness check
            await asyncio.wait_for(
                self._wait_for_ready(),
                timeout=self.startup_timeout
            )
            
            self._is_running = True
            logger.info("✅ Container environment ready")
            
        except asyncio.TimeoutError:
            logger.error(f"❌ Container startup timed out after {self.startup_timeout}s")
            raise RuntimeError(f"Container startup timed out after {self.startup_timeout}s")
        except Exception as e:
            logger.error(f"Failed to start containers: {e}")
            raise RuntimeError(f"Container startup failed: {e}")

    async def _wait_for_ready(self, max_attempts: int = 30) -> None:
        """Wait for container readiness with attempt limit."""
        logger.info(f"🔍 Waiting for container {self.container_name} to be ready...")
        
        for attempt in range(max_attempts):
            try:
                # ✅ Check if container exists with timeout
                check_process = await asyncio.wait_for(
                    asyncio.create_subprocess_exec(
                        "podman", "ps", "--filter", f"name={self.container_name}",
                        "--format", "{{.Names}}",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    ),
                    timeout=10
                )
                
                stdout, stderr = await asyncio.wait_for(
                    check_process.communicate(),
                    timeout=10
                )
                
                if self.container_name in stdout.decode():
                    try:
                        # ✅ Test container responsiveness
                        await asyncio.wait_for(
                            self.execute(["python", "--version"]),
                            timeout=10
                        )
                        logger.info(f"✅ Container ready after {attempt + 1} attempts")
                        return
                    except (RuntimeError, asyncio.TimeoutError):
                        # Container exists but not ready yet
                        pass
                    
            except asyncio.TimeoutError:
                logger.warning(f"⚠️  Container check timed out on attempt {attempt + 1}")
            except Exception as e:
                logger.debug(f"Container check failed on attempt {attempt + 1}: {e}")
            
            # ✅ Non-blocking sleep between attempts
            await asyncio.sleep(2)
            
        raise TimeoutError(f"Container {self.container_name} failed to become ready after {max_attempts} attempts")

    async def execute(self, command: List[str]) -> str:
        """Execute command with timeout protection."""
        if not self._is_running:
            raise RuntimeError("Container is not running")
        
        full_command = ["podman", "exec", self.container_name] + command
        
        try:
            # ✅ Add timeout to command execution
            process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *full_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=self.command_timeout
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.command_timeout
            )
            
            if process.returncode != 0:
                logger.error(f"Command failed: {' '.join(command)}")
                logger.error(f"Stderr: {stderr.decode()}")
                raise RuntimeError(f"Container command failed: {stderr.decode()}")
                
            return stdout.decode()
            
        except asyncio.TimeoutError:
            logger.error(f"Command timed out after {self.command_timeout}s: {' '.join(command)}")
            raise RuntimeError(f"Command timed out: {' '.join(command)}")
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise RuntimeError(f"Container command failed: {e}")

    async def cleanup(self) -> None:
        """Cleanup with timeout protection."""
        if not self._is_running:
            return
            
        logger.info("🧹 Cleaning up containers...")
        try:
            # ✅ Add timeout to cleanup
            process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "podman-compose", "-f", str(self.compose_file),
                    "down", "-v", "--remove-orphans",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=30
            )
            await asyncio.wait_for(process.communicate(), timeout=30)
        except asyncio.TimeoutError:
            logger.warning("Cleanup timed out - forcing container removal")
            # Force cleanup without waiting
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")
        finally:
            self._is_running = False
