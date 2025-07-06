# 🚀 MCP Server Development Best Practices & Rules

## 🎯 Core FastMCP Principles

### Server Architecture
```python
# ✅ Proper FastMCP server setup
from fastmcp import FastMCP

# Create server with clear name and instructions
mcp = FastMCP(
    name="My Production Server",
    instructions="Clear description of server capabilities"
)

# Use decorators for tools and resources
@mcp.tool
async def process_data(input_data: str) -> dict:
    """Process data with clear documentation."""
    return {"result": processed_data}

@mcp.resource("data://config")
def get_config() -> dict:
    """Provide configuration data."""
    return {"version": "1.0", "env": "production"}
```

### Method Registration Patterns
```python
# ✅ GOOD: Register instance methods properly
class DataProcessor:
    def __init__(self, mcp_instance):
        # Register bound methods
        mcp_instance.tool(self.process)
        mcp_instance.resource("data://status")(self.get_status)
    
    def process(self, data: str) -> str:
        return f"Processed: {data}"
    
    def get_status(self) -> dict:
        return {"status": "active"}

# Create instance and register
processor = DataProcessor(mcp)

# ✅ GOOD: Register static methods
class Utilities:
    @staticmethod
    def calculate(x: int, y: int) -> int:
        return x + y

mcp.tool(Utilities.calculate)

# ❌ BAD: Direct decoration of instance methods
class BadExample:
    @mcp.tool  # This won't work correctly
    def method(self, x: int) -> int:
        return x * 2
```

## 🔒 Security Best Practices

### Authentication & Authorization
```python
# ✅ Implement proper authentication
from fastmcp.server.middleware import Middleware
import jwt

class AuthMiddleware(Middleware):
    async def on_request(self, context, call_next):
        token = context.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            raise McpError(ErrorData(code=-32001, message="Authentication required"))
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            context.user_id = payload["user_id"]
        except jwt.InvalidTokenError:
            raise McpError(ErrorData(code=-32001, message="Invalid token"))
        
        return await call_next(context)

mcp.add_middleware(AuthMiddleware())
```

### Input Validation
```python
# ✅ Use Pydantic for robust validation
from pydantic import BaseModel, Field, validator
from typing import Literal

class ProcessRequest(BaseModel):
    data: str = Field(..., min_length=1, max_length=1000)
    operation: Literal["analyze", "transform", "validate"]
    timeout: int = Field(default=30, ge=1, le=300)
    
    @validator('data')
    def validate_data(cls, v):
        if not v.strip():
            raise ValueError("Data cannot be empty")
        return v

@mcp.tool
async def process_with_validation(request: ProcessRequest) -> dict:
    """Process data with comprehensive validation."""
    # Input is already validated by Pydantic
    return await process_data(request.data, request.operation)
```

### Error Handling
```python
# ✅ Comprehensive error handling
from mcp import McpError
from mcp.types import ErrorData
import logging

@mcp.tool
async def safe_operation(data: str) -> dict:
    """Operation with proper error handling."""
    try:
        # Always validate inputs
        if not data.strip():
            raise McpError(ErrorData(
                code=-32602,
                message="Invalid parameters: data cannot be empty"
            ))
        
        # Use timeouts for external operations
        async with asyncio.timeout(30):
            result = await external_api_call(data)
        
        return {"result": result}
        
    except asyncio.TimeoutError:
        logger.warning(f"Operation timed out for data: {data[:50]}")
        raise McpError(ErrorData(
            code=-32000,
            message="Operation timed out"
        ))
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        # Never expose internal errors to clients
        raise McpError(ErrorData(
            code=-32000,
            message="Internal server error"
        ))
```

## 🏗️ Advanced Architecture Patterns

### Resource Templates & Dynamic Content
```python
# ✅ Parameterized resources
@mcp.resource("users://{user_id}/profile")
def get_user_profile(user_id: int) -> dict:
    """Retrieve user profile by ID."""
    return find_user_by_id(user_id)

# ✅ Multiple URI patterns for same resource
@mcp.resource("users://email/{email}")
@mcp.resource("users://name/{name}")
def lookup_user(name: str | None = None, email: str | None = None) -> dict:
    """Look up user by name or email."""
    if email:
        return find_user_by_email(email)
    elif name:
        return find_user_by_name(name)
    return {"error": "No lookup parameters provided"}
```

### Middleware Architecture
```python
# ✅ Custom logging middleware
class LoggingMiddleware(Middleware):
    async def on_request(self, context, call_next):
        start_time = time.perf_counter()
        logger.info(f"Processing {context.method}")
        
        try:
            result = await call_next(context)
            duration = time.perf_counter() - start_time
            logger.info(f"Completed {context.method} in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(f"Failed {context.method} after {duration:.3f}s: {e}")
            raise

# ✅ Rate limiting middleware
class RateLimitMiddleware(Middleware):
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.client_requests = defaultdict(list)
    
    async def on_request(self, context, call_next):
        client_id = context.headers.get("x-client-id", "default")
        current_time = time.time()
        
        # Clean old requests
        cutoff_time = current_time - 60
        self.client_requests[client_id] = [
            req_time for req_time in self.client_requests[client_id]
            if req_time > cutoff_time
        ]
        
        if len(self.client_requests[client_id]) >= self.requests_per_minute:
            raise McpError(ErrorData(code=-32000, message="Rate limit exceeded"))
        
        self.client_requests[client_id].append(current_time)
        return await call_next(context)

# Apply middleware
mcp.add_middleware(LoggingMiddleware())
mcp.add_middleware(RateLimitMiddleware(requests_per_minute=100))
```

### Context & Elicitation
```python
# ✅ Using context for advanced operations
from fastmcp.server.context import Context

@mcp.tool
async def interactive_process(query: str, ctx: Context) -> str:
    """Interactive processing with user confirmation."""
    
    # Elicit user confirmation
    result = await ctx.elicit(
        "Proceed with destructive operation?",
        response_type=bool
    )
    
    match result:
        case AcceptedElicitation(data=True):
            return await perform_operation(query)
        case AcceptedElicitation(data=False) | DeclinedElicitation():
            return "Operation cancelled by user"
        case CancelledElicitation():
            return "Operation was cancelled"

# ✅ Multi-turn conversations
@mcp.tool
async def complex_analysis(data: str, ctx: Context) -> str:
    """Perform complex analysis with LLM assistance."""
    messages = [
        SamplingMessage(role="user", content=f"Analyze this data: {data}"),
        SamplingMessage(role="assistant", content="I need more context. What type of analysis?"),
        SamplingMessage(role="user", content="Performance analysis focusing on bottlenecks")
    ]
    
    response = await ctx.sample(
        messages=messages,
        system_prompt="You are a performance analysis expert.",
        temperature=0.3
    )
    
    return response.text
```

## 🚀 Performance Optimization

### Async Patterns
```python
# ✅ Efficient concurrent operations
@mcp.tool
async def batch_process(items: list[str]) -> list[dict]:
    """Process multiple items concurrently."""
    
    # Use semaphore for bounded concurrency
    semaphore = asyncio.Semaphore(10)
    
    async def process_item(item: str) -> dict:
        async with semaphore:
            return await heavy_processing(item)
    
    tasks = [process_item(item) for item in items]
    return await asyncio.gather(*tasks)

# ✅ Caching for expensive operations
from functools import lru_cache
import asyncio

class CachedProcessor:
    def __init__(self):
        self._cache = {}
    
    async def expensive_operation(self, key: str) -> dict:
        if key in self._cache:
            return self._cache[key]
        
        result = await actual_expensive_operation(key)
        self._cache[key] = result
        return result
```

### Resource Management
```python
# ✅ Proper resource cleanup
class DatabaseTool:
    def __init__(self):
        self.pool = None
    
    async def setup(self):
        self.pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20
        )
    
    async def cleanup(self):
        if self.pool:
            await self.pool.close()
    
    @mcp.tool
    async def query_data(self, sql: str) -> list[dict]:
        """Execute database query."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql)
            return [dict(row) for row in rows]
```

## 🧪 Testing Patterns

### FastMCP Testing
```python
# ✅ Comprehensive server testing
import pytest
from fastmcp.testing import TestClient

@pytest.fixture
async def test_client():
    mcp = FastMCP("Test Server")
    
    @mcp.tool
    async def test_tool(x: int) -> int:
        return x * 2
    
    async with TestClient(mcp) as client:
        yield client

@pytest.mark.asyncio
async def test_tool_execution(test_client):
    result = await test_client.call_tool("test_tool", {"x": 5})
    assert result == 10

# ✅ Testing middleware
@pytest.mark.asyncio
async def test_middleware_behavior():
    middleware_called = False
    
    class TestMiddleware(Middleware):
        async def on_request(self, context, call_next):
            nonlocal middleware_called
            middleware_called = True
            return await call_next(context)
    
    mcp = FastMCP("Test")
    mcp.add_middleware(TestMiddleware())
    
    @mcp.tool
    def simple_tool() -> str:
        return "test"
    
    async with TestClient(mcp) as client:
        await client.call_tool("simple_tool", {})
        assert middleware_called
```

## 🐳 Production Deployment

### Docker Configuration
```dockerfile
# ✅ Production-ready Dockerfile
FROM python:3.12-slim

# Security: Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Install dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run server
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Configuration
```python
# ✅ Production configuration
import os
from typing import Optional

class Settings:
    # Server configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    WORKERS: int = int(os.getenv("WORKERS", "4"))
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALLOWED_ORIGINS: list[str] = os.getenv("ALLOWED_ORIGINS", "").split(",")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Performance
    MAX_CONNECTIONS: int = int(os.getenv("MAX_CONNECTIONS", "100"))
    TIMEOUT: int = int(os.getenv("TIMEOUT", "30"))
    
    def __post_init__(self):
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY environment variable required")

settings = Settings()

# ✅ Production server setup
def create_production_app():
    mcp = FastMCP(
        name="Production MCP Server",
        instructions="Production-ready MCP server with security and monitoring"
    )
    
    # Add production middleware
    mcp.add_middleware(AuthMiddleware())
    mcp.add_middleware(RateLimitMiddleware(100))
    mcp.add_middleware(LoggingMiddleware())
    
    return mcp
```

## 📋 Production Checklist

### Security
- [ ] Authentication middleware implemented
- [ ] Input validation with Pydantic
- [ ] Rate limiting configured
- [ ] Secrets managed via environment variables
- [ ] Non-root Docker user configured
- [ ] HTTPS/TLS enabled
- [ ] Error messages sanitized

### Performance
- [ ] Async patterns used throughout
- [ ] Connection pooling implemented
- [ ] Caching for expensive operations
- [ ] Bounded concurrency configured
- [ ] Resource cleanup implemented
- [ ] Health checks configured

### Monitoring
- [ ] Comprehensive logging middleware
- [ ] Error tracking and metrics
- [ ] Performance monitoring
- [ ] Health check endpoints
- [ ] Graceful shutdown handling

### Testing
- [ ] Unit tests for all tools/resources
- [ ] Integration tests with TestClient
- [ ] Middleware testing
- [ ] Error handling tests
- [ ] Performance tests

## 🚫 Common Antipatterns

### ❌ Don't expose internal errors
```python
# ❌ BAD: Exposing internal details
@mcp.tool
async def bad_error_handling(data: str):
    try:
        return await process(data)
    except Exception as e:
        return f"Error: {str(e)}"  # Exposes internal details

# ✅ GOOD: Sanitized error responses
@mcp.tool
async def good_error_handling(data: str):
    try:
        return await process(data)
    except ValidationError:
        raise McpError(ErrorData(code=-32602, message="Invalid input"))
    except Exception as e:
        logger.error(f"Internal error: {e}")
        raise McpError(ErrorData(code=-32000, message="Internal server error"))
```

### ❌ Don't hardcode secrets
```python
# ❌ BAD: Hardcoded credentials
API_KEY = "sk-1234567890abcdef"  # Never do this

# ✅ GOOD: Environment-based configuration
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable required")
```

### ❌ Don't ignore async best practices
```python
# ❌ BAD: Blocking operations in async context
@mcp.tool
async def blocking_operation():
    time.sleep(5)  # Blocks event loop
    return requests.get(url).json()  # Blocking I/O

# ✅ GOOD: Proper async operations
@mcp.tool
async def non_blocking_operation():
    await asyncio.sleep(5)  # Non-blocking
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()
``` 