# tests/container_manager.py
"""
Async container manager for E2E testing.
"""
import asyncio
import subprocess
import logging
from pathlib import Path
from typing import List, Optional
from typing import Dict, Any

try:
    import uvloop
    UVLOOP_AVAILABLE = True
except ImportError:
    UVLOOP_AVAILABLE = False
    logging.warning("uvloop not available, falling back to default asyncio event loop")

logger = logging.getLogger(__name__)

class AsyncContainerManager:
    """High-performance async container lifecycle management."""
    
    def __init__(
        self, 
        compose_file: Path, 
        service_name: str = "mcp-server",
        use_uvloop: bool = True
    ):
        self.compose_file = compose_file
        self.service_name = service_name
        self.container_name = f"helmconfoigdecomission_{service_name}_1"
        self._is_running = False
        self.use_uvloop = use_uvloop and UVLOOP_AVAILABLE
        
        if self.use_uvloop:
            logger.info("🚀 Using uvloop for enhanced performance")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def start(self) -> None:
        """Build and start containers asynchronously."""
        logger.info("🚀 Starting container environment...")
        try:
            process = await asyncio.create_subprocess_exec(
                "podman-compose", "-f", str(self.compose_file),
                "up", "--build", "-d",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 1024  # 1MB buffer limit
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise RuntimeError(f"Container startup failed: {stderr.decode()}")
                
            await self._wait_for_ready()
            self._is_running = True
            logger.info("✅ Container environment ready")
            
        except Exception as e:
            logger.error(f"Failed to start containers: {e}")
            raise RuntimeError(f"Container startup failed: {e}")

    async def cleanup(self) -> None:
        """Clean shutdown asynchronously."""
        if not self._is_running:
            return
        logger.info("🧹 Cleaning up containers...")
        try:
            process = await asyncio.create_subprocess_exec(
                "podman-compose", "-f", str(self.compose_file),
                "down", "-v", "--remove-orphans",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")
        finally:
            self._is_running = False

    async def _wait_for_ready(self, timeout: int = 30) -> None:
        """Wait for container to be ready asynchronously."""
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                process = await asyncio.create_subprocess_exec(
                    "podman", "ps", "--filter", f"name={self.container_name}",
                    "--format", "{{.Names}}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    limit=1024 * 64  # Smaller buffer for quick checks
                )
                stdout, stderr = await process.communicate()
                
                if self.container_name in stdout.decode():
                    try:
                        await self.execute(["python", "--version"])
                        return
                    except RuntimeError:
                        pass
                    
            except Exception:
                pass
            
            await asyncio.sleep(1)
            
        raise TimeoutError(f"Container failed to become ready within {timeout}s")

    async def execute(self, command: List[str]) -> str:
        """Execute command with uvloop optimization."""
        if not self._is_running:
            raise RuntimeError("Container is not running")
        
        full_command = ["podman", "exec", self.container_name] + command
        
        try:
            process = await asyncio.create_subprocess_exec(
                *full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 1024  # 1MB buffer for command output
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Command failed: {' '.join(command)}")
                logger.error(f"Stderr: {stderr.decode()}")
                raise RuntimeError(f"Container command failed: {stderr.decode()}")
                
            return stdout.decode()
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise RuntimeError(f"Container command failed: {e}")

class AsyncE2ETestSuite:
    """Helper for async E2E test suites."""
    
    def __init__(self, compose_file: Path):
        self.compose_file = compose_file
        self.results: List[Dict[str, Any]] = []

    async def run_test_scenario(self, name: str, test_func, *args, **kwargs) -> Dict[str, Any]:
        """Run a single test scenario asynchronously."""
        logger.info(f"🧪 Running test scenario: {name}")
        
        result = {
            "name": name,
            "success": False,
            "error": None,
            "duration": 0
        }
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            async with AsyncContainerManager(self.compose_file) as container:
                await test_func(container, *args, **kwargs)
                result["success"] = True
                logger.info(f"✅ Test scenario '{name}' passed")
                
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"❌ Test scenario '{name}' failed: {e}")
        
        finally:
            result["duration"] = asyncio.get_event_loop().time() - start_time
            self.results.append(result)
        
        return result
    
    def get_summary(self) -> Dict[str, Any]:
        """Get test suite summary."""
        total = len(self.results)
        failed = sum(1 for r in self.results if not r["success"])
        return {
            "total": total,
            "passed": total - failed,
            "failed": failed,
            "success_rate": (total - failed) / total if total > 0 else 0
        }
