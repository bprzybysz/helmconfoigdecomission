# 🔄 Async/Await Python Best Practices & Rules

## 🎯 Core Principles

### ✅ DO: Use async/await for I/O-bound tasks
```python
# ✅ Good - I/O-bound operations
async def fetch_data():
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

async def read_file():
    async with aiofiles.open("file.txt") as f:
        return await f.read()
```

### ❌ DON'T: Use async for CPU-bound tasks
```python
# ❌ Bad - CPU-bound work blocks event loop
async def cpu_intensive():
    return sum(i**2 for i in range(1000000))

# ✅ Good - Offload to threads
async def cpu_intensive():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: sum(i**2 for i in range(1000000)))
```

## 🏗️ Architecture Patterns

### Concurrent Operations
```python
# ✅ Use asyncio.gather for concurrent tasks
async def fetch_multiple():
    tasks = [
        fetch_data(url1),
        fetch_data(url2), 
        fetch_data(url3)
    ]
    return await asyncio.gather(*tasks)

# ✅ Use asyncio.as_completed for processing as they complete
async def process_as_ready():
    tasks = [fetch_data(url) for url in urls]
    for coro in asyncio.as_completed(tasks):
        result = await coro
        process_result(result)
```

### Resource Management
```python
# ✅ Always use async context managers
async def proper_resource_handling():
    async with database.connection() as conn:
        async with conn.transaction():
            result = await conn.execute(query)
            return result
```

### Error Handling
```python
# ✅ Comprehensive error handling
async def robust_async_function():
    try:
        async with timeout(30):  # Always set timeouts
            result = await external_api_call()
            return result
    except asyncio.TimeoutError:
        logger.warning("API call timed out")
        raise
    except Exception as e:
        logger.error(f"API call failed: {e}")
        raise
```

## 🧪 pytest-asyncio Testing Rules

### Test Function Patterns
```python
# ✅ Mark async tests properly
@pytest.mark.asyncio
async def test_async_function():
    result = await my_async_function()
    assert result == expected

# ✅ Use async fixtures
@pytest.fixture
async def async_client():
    async with httpx.AsyncClient() as client:
        yield client

@pytest.mark.asyncio
async def test_with_client(async_client):
    response = await async_client.get("/api/test")
    assert response.status_code == 200
```

### Concurrent Testing
```python
# ✅ Test concurrent behavior
@pytest.mark.asyncio
async def test_concurrent_operations():
    tasks = [
        process_item(1),
        process_item(2),
        process_item(3)
    ]
    results = await asyncio.gather(*tasks)
    assert len(results) == 3
```

### Fixture Scopes
```python
# ✅ Choose appropriate fixture scopes
@pytest.fixture(scope="session")
async def event_loop():
    """Create event loop for the test session"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")  # Default, ensures isolation
async def db_transaction():
    async with database.transaction() as txn:
        yield txn
        await txn.rollback()  # Always rollback in tests
```

## ⚡ Performance Optimization

### uvloop Integration
```python
# ✅ Use uvloop for production performance
import uvloop
import asyncio

# Set as default event loop policy
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# Or use explicitly
async def main():
    # Your async code here
    pass

if __name__ == "__main__":
    uvloop.run(main())
```

### Connection Pooling
```python
# ✅ Use connection pools for databases/HTTP
class DatabaseManager:
    def __init__(self):
        self.pool = None
    
    async def setup(self):
        self.pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
    
    async def fetch(self, query):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query)
```

### Bounded Concurrency
```python
# ✅ Use semaphores to limit concurrent operations
async def limited_concurrent_requests():
    semaphore = asyncio.Semaphore(10)  # Max 10 concurrent
    
    async def bounded_request(url):
        async with semaphore:
            return await fetch_data(url)
    
    tasks = [bounded_request(url) for url in urls]
    return await asyncio.gather(*tasks)
```

## 🚫 Common Pitfalls & Solutions

### Blocking the Event Loop
```python
# ❌ Bad - Blocking operations
async def bad_example():
    time.sleep(1)  # Blocks event loop!
    requests.get(url)  # Blocks event loop!

# ✅ Good - Non-blocking alternatives
async def good_example():
    await asyncio.sleep(1)  # Non-blocking
    async with httpx.AsyncClient() as client:
        response = await client.get(url)  # Non-blocking
```

### Exception Handling
```python
# ❌ Bad - Silent failures
async def bad_error_handling():
    task = asyncio.create_task(risky_operation())
    # Task exception will be lost if not awaited

# ✅ Good - Proper exception handling
async def good_error_handling():
    try:
        task = asyncio.create_task(risky_operation())
        result = await task
        return result
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        raise
```

### Context Manager Issues
```python
# ❌ Bad - Not awaiting async context managers
async def bad_context():
    with async_resource():  # Missing 'async'
        pass

# ✅ Good - Proper async context manager usage
async def good_context():
    async with async_resource():
        pass
```

## 🔧 Configuration Best Practices

### pytest.ini Configuration
```ini
[tool:pytest]
asyncio_mode = auto
markers =
    asyncio: mark test as async
    slow: mark test as slow running
testpaths = tests
addopts = 
    --strict-markers
    --strict-config
    --cov=src
    --cov-branch
    --cov-report=term-missing
    --asyncio-mode=auto
```

### pyproject.toml Configuration
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "asyncio",
    "slow: marks tests as slow",
]

[tool.coverage.run]
concurrency = ["thread", "greenlet"]
```

## 📋 Checklist for Async Code Review

- [ ] All I/O operations use async/await
- [ ] No blocking calls in async functions
- [ ] Proper error handling with try/except
- [ ] Timeouts set for external operations
- [ ] Resource cleanup with async context managers
- [ ] Tests marked with @pytest.mark.asyncio
- [ ] Async fixtures used where appropriate
- [ ] uvloop configured for production
- [ ] Connection pooling implemented
- [ ] Bounded concurrency for external calls
- [ ] All async context managers properly awaited
- [ ] No silent task failures

## 🎯 Production Deployment

### Environment Configuration
```python
# ✅ Production-ready async app
import uvloop
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # Startup
    await database.connect()
    await cache.connect()
    yield
    # Shutdown
    await database.disconnect()
    await cache.disconnect()

def create_app():
    # Set uvloop as default
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    
    app = FastAPI(lifespan=lifespan)
    return app
```

### Monitoring & Observability
```python
# ✅ Add timing and monitoring
import time
from functools import wraps

def async_timer(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            duration = time.perf_counter() - start
            logger.info(f"{func.__name__} completed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.perf_counter() - start
            logger.error(f"{func.__name__} failed after {duration:.3f}s: {e}")
            raise
    return wrapper
``` 