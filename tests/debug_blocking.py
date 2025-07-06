# tests/debug_blocking.py
import asyncio
import logging
import time
from functools import wraps

class BlockingDetector:
    def __init__(self, threshold=0.1):
        self.threshold = threshold
        
    def detect_blocking(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            duration = time.perf_counter() - start
            
            if duration > self.threshold:
                logging.warning(f"⚠️  {func.__name__} took {duration:.3f}s - potentially blocking!")
                
            return result
        return wrapper

# Enable asyncio debug mode
def setup_async_debugging():
    logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.slow_callback_duration = 0.1  # 100ms threshold
