# 🧪 Python Testing Best Practices & Rules

## 🎯 Core Testing Principles

### Test Organization
```python
# ✅ Organize tests by functionality
tests/
├── conftest.py              # Shared fixtures
├── test_auth/              # Authentication tests
│   ├── test_login.py
│   └── test_permissions.py
├── test_api/               # API endpoint tests
│   ├── test_users.py
│   └── test_payments.py
└── test_models/            # Model/business logic tests
    ├── test_user_model.py
    └── test_payment_model.py

# ✅ Descriptive test names
def test_user_login_succeeds_with_valid_credentials():
    """Test that users can log in with correct username/password."""
    pass

def test_user_login_fails_with_invalid_password():
    """Test that login fails when password is incorrect."""
    pass

def test_payment_processing_handles_insufficient_funds():
    """Test that payment fails gracefully when balance is too low."""
    pass
```

### Test Structure (AAA Pattern)
```python
# ✅ Arrange, Act, Assert pattern
def test_user_creation_sets_default_values():
    # Arrange
    username = "testuser"
    email = "test@example.com"
    
    # Act
    user = User.create(username=username, email=email)
    
    # Assert
    assert user.username == username
    assert user.email == email
    assert user.is_active is True
    assert user.created_at is not None
```

## 🔧 pytest Configuration

### pyproject.toml Configuration
```toml
[tool.pytest.ini_options]
minversion = "7.0"
addopts = [
    "--strict-markers",
    "--strict-config", 
    "--cov=src",
    "--cov-branch",
    "--cov-report=term-missing:skip-covered",
    "--cov-report=html",
    "--cov-fail-under=90",
    "-ra",  # Show short test summary for all except passed
    "--tb=short",
]
testpaths = ["tests"]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
    "asyncio: marks tests as async",
]
asyncio_mode = "auto"
filterwarnings = [
    "error",
    "ignore::UserWarning",
    "ignore::DeprecationWarning",
]

[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/migrations/*",
    "*/venv/*",
    "*/__pycache__/*",
]
concurrency = ["thread", "greenlet"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if self.debug:",
    "if settings.DEBUG",
    "raise AssertionError",
    "raise NotImplementedError",
    "if 0:",
    "if __name__ == .__main__.:",
    "class .*\\bProtocol\\):",
    "@(abc\\.)?abstractmethod",
]
```

## 🏗️ Fixture Patterns

### Basic Fixtures
```python
# ✅ conftest.py - Shared fixtures
import pytest
import asyncio
from unittest.mock import Mock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def db_session():
    """Provide database session with rollback."""
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.rollback()
    session.close()

@pytest.fixture
def mock_external_api():
    """Mock external API calls."""
    return Mock()

# ✅ Fixture scopes
@pytest.fixture(scope="session")  # Once per test session
def database_url():
    return "postgresql://test:test@localhost/testdb"

@pytest.fixture(scope="module")   # Once per test module
def app_config():
    return {"DEBUG": True, "TESTING": True}

@pytest.fixture(scope="class")    # Once per test class
def api_client():
    return TestClient()

@pytest.fixture(scope="function") # Once per test function (default)
def user():
    return User(username="testuser", email="test@example.com")
```

### Advanced Fixture Patterns
```python
# ✅ Parameterized fixtures
@pytest.fixture(params=[
    {"role": "admin", "permissions": ["read", "write", "delete"]},
    {"role": "user", "permissions": ["read"]},
    {"role": "guest", "permissions": []},
])
def user_with_role(request):
    """Fixture that provides users with different roles."""
    return User(**request.param)

# ✅ Factory fixtures
@pytest.fixture
def user_factory(db_session):
    """Factory for creating users."""
    created_users = []
    
    def _create_user(**kwargs):
        defaults = {"username": "testuser", "email": "test@example.com"}
        defaults.update(kwargs)
        user = User(**defaults)
        db_session.add(user)
        db_session.commit()
        created_users.append(user)
        return user
    
    yield _create_user
    
    # Cleanup
    for user in created_users:
        db_session.delete(user)
    db_session.commit()

# ✅ Conditional fixtures
@pytest.fixture
def authenticated_user(request, user_factory):
    """Create authenticated user only when needed."""
    if hasattr(request, "param") and request.param.get("auth_required"):
        return user_factory(is_authenticated=True)
    return None
```

## 🔄 Async Testing with pytest-asyncio

### Basic Async Testing
```python
# ✅ Async test functions
@pytest.mark.asyncio
async def test_async_function():
    result = await async_operation()
    assert result == expected_value

# ✅ Async fixtures
@pytest.fixture
async def async_client():
    """Async HTTP client fixture."""
    async with httpx.AsyncClient() as client:
        yield client

@pytest.fixture
async def db_connection():
    """Async database connection."""
    conn = await asyncpg.connect(DATABASE_URL)
    yield conn
    await conn.close()

@pytest.mark.asyncio
async def test_with_async_fixtures(async_client, db_connection):
    response = await async_client.get("/api/users")
    assert response.status_code == 200
    
    users = await db_connection.fetch("SELECT * FROM users")
    assert len(users) > 0
```

### Concurrent Testing
```python
# ✅ Test concurrent operations
@pytest.mark.asyncio
async def test_concurrent_requests():
    """Test system behavior under concurrent load."""
    async with httpx.AsyncClient() as client:
        tasks = [
            client.get("/api/data/1"),
            client.get("/api/data/2"),
            client.get("/api/data/3"),
        ]
        responses = await asyncio.gather(*tasks)
        
        for response in responses:
            assert response.status_code == 200

@pytest.mark.asyncio
async def test_rate_limiting():
    """Test that rate limiting works correctly."""
    async with httpx.AsyncClient() as client:
        # Make rapid requests
        tasks = [client.get("/api/limited") for _ in range(100)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Some should succeed, some should be rate limited
        success_count = sum(1 for r in responses if hasattr(r, 'status_code') and r.status_code == 200)
        rate_limited_count = sum(1 for r in responses if hasattr(r, 'status_code') and r.status_code == 429)
        
        assert success_count > 0
        assert rate_limited_count > 0
```

## 🎭 Mocking with pytest-mock

### Basic Mocking Patterns
```python
# ✅ Mock external dependencies
def test_email_sending(mocker):
    """Test email sending without actually sending emails."""
    mock_send = mocker.patch("app.email.send_email")
    mock_send.return_value = True
    
    result = send_welcome_email("test@example.com")
    
    assert result is True
    mock_send.assert_called_once_with(
        to="test@example.com",
        subject="Welcome!",
        template="welcome.html"
    )

# ✅ Mock with side effects
def test_retry_logic(mocker):
    """Test retry logic with intermittent failures."""
    mock_api = mocker.patch("app.external.api_call")
    mock_api.side_effect = [
        ConnectionError("Network error"),
        ConnectionError("Network error"),
        {"status": "success"}  # Third call succeeds
    ]
    
    result = robust_api_call()
    
    assert result == {"status": "success"}
    assert mock_api.call_count == 3

# ✅ Context manager mocking
def test_file_processing(mocker):
    """Test file processing with mocked file operations."""
    mock_open = mocker.mock_open(read_data="test data")
    mocker.patch("builtins.open", mock_open)
    
    result = process_file("test.txt")
    
    assert result == "processed: test data"
    mock_open.assert_called_once_with("test.txt", "r")
```

### Advanced Mocking
```python
# ✅ Mock class methods and properties
def test_user_service(mocker):
    """Test service with mocked dependencies."""
    mock_db = mocker.Mock()
    mock_db.get_user.return_value = User(id=1, name="Test")
    mock_db.save_user.return_value = True
    
    service = UserService(database=mock_db)
    result = service.update_user(1, {"name": "Updated"})
    
    assert result is True
    mock_db.get_user.assert_called_once_with(1)
    mock_db.save_user.assert_called_once()

# ✅ Mock async functions
@pytest.mark.asyncio
async def test_async_service(mocker):
    """Test async service with mocked dependencies."""
    mock_fetch = mocker.patch("app.service.fetch_data")
    mock_fetch.return_value = asyncio.Future()
    mock_fetch.return_value.set_result({"data": "test"})
    
    result = await process_async_data("query")
    
    assert result["data"] == "test"
    mock_fetch.assert_called_once_with("query")

# ✅ Spy on existing methods
def test_caching_behavior(mocker):
    """Test that caching works by spying on expensive operations."""
    spy = mocker.spy(ExpensiveService, "calculate")
    service = CachedService()
    
    # First call should hit the expensive service
    result1 = service.get_result("input")
    assert spy.call_count == 1
    
    # Second call should use cache
    result2 = service.get_result("input")
    assert spy.call_count == 1  # Still 1, not called again
    assert result1 == result2
```

## 🗃️ Database Testing Patterns

### Transaction-based Testing
```python
# ✅ Test with database transactions
@pytest.fixture
def db_transaction(db_engine):
    """Provide database transaction that rolls back after test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    
    yield connection
    
    transaction.rollback()
    connection.close()

def test_user_creation(db_transaction):
    """Test user creation with automatic rollback."""
    user = User(username="test", email="test@example.com")
    db_transaction.execute(
        "INSERT INTO users (username, email) VALUES (?, ?)",
        (user.username, user.email)
    )
    
    result = db_transaction.execute(
        "SELECT * FROM users WHERE username = ?", 
        (user.username,)
    ).fetchone()
    
    assert result is not None
    assert result["email"] == user.email
    # Transaction automatically rolls back after test
```

### Test Data Factories
```python
# ✅ Use factories for test data
import factory
from factory import Faker

class UserFactory(factory.Factory):
    class Meta:
        model = User
    
    username = Faker("user_name")
    email = Faker("email")
    first_name = Faker("first_name")
    last_name = Faker("last_name")
    is_active = True
    created_at = Faker("date_time_this_year")

class PostFactory(factory.Factory):
    class Meta:
        model = Post
    
    title = Faker("sentence", nb_words=4)
    content = Faker("text", max_nb_chars=500)
    author = factory.SubFactory(UserFactory)
    published_at = Faker("date_time_this_month")

# ✅ Use factories in tests
def test_user_post_relationship():
    """Test relationship between users and posts."""
    user = UserFactory()
    post = PostFactory(author=user)
    
    assert post.author == user
    assert post.title is not None
    assert len(post.content) > 0

def test_multiple_posts():
    """Test creating multiple related objects."""
    author = UserFactory()
    posts = PostFactory.create_batch(5, author=author)
    
    assert len(posts) == 5
    assert all(post.author == author for post in posts)
```

## 🚀 Performance Testing

### Timing and Benchmarking
```python
# ✅ Performance testing with timing
import time
import pytest

def test_function_performance():
    """Test that function completes within acceptable time."""
    start_time = time.perf_counter()
    
    result = expensive_operation()
    
    duration = time.perf_counter() - start_time
    assert duration < 1.0  # Should complete in under 1 second
    assert result is not None

@pytest.mark.benchmark
def test_algorithm_performance(benchmark):
    """Benchmark algorithm performance."""
    data = list(range(1000))
    
    result = benchmark(sort_algorithm, data)
    
    assert result == sorted(data)

# ✅ Memory usage testing
import tracemalloc

def test_memory_usage():
    """Test that operation doesn't use excessive memory."""
    tracemalloc.start()
    
    large_operation()
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # Assert memory usage is reasonable (e.g., under 100MB)
    assert peak < 100 * 1024 * 1024
```

## 🔍 Integration Testing

### API Testing
```python
# ✅ API integration tests
@pytest.fixture
def app():
    """Create test application."""
    app = create_app(config="testing")
    return app

@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()

def test_user_registration_flow(client):
    """Test complete user registration flow."""
    # Register new user
    response = client.post("/api/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "securepassword123"
    })
    assert response.status_code == 201
    user_data = response.get_json()
    assert user_data["username"] == "newuser"
    
    # Verify user can login
    response = client.post("/api/login", json={
        "username": "newuser",
        "password": "securepassword123"
    })
    assert response.status_code == 200
    token = response.get_json()["token"]
    
    # Use token to access protected resource
    response = client.get("/api/profile", headers={
        "Authorization": f"Bearer {token}"
    })
    assert response.status_code == 200
    profile = response.get_json()
    assert profile["username"] == "newuser"

# ✅ Error handling tests
def test_api_error_handling(client):
    """Test API error responses."""
    # Test validation errors
    response = client.post("/api/users", json={
        "username": "",  # Invalid: empty username
        "email": "invalid-email"  # Invalid: bad email format
    })
    assert response.status_code == 400
    errors = response.get_json()["errors"]
    assert "username" in errors
    assert "email" in errors
    
    # Test authentication errors
    response = client.get("/api/protected")
    assert response.status_code == 401
    
    # Test not found errors
    response = client.get("/api/users/99999")
    assert response.status_code == 404
```

## 🎭 Test Categories and Markers

### Organizing Tests by Speed
```python
# ✅ Mark slow tests
@pytest.mark.slow
def test_full_data_migration():
    """Test complete data migration (takes several minutes)."""
    migrate_all_data()
    assert migration_complete()

@pytest.mark.integration
def test_payment_gateway_integration():
    """Test integration with external payment gateway."""
    result = process_payment_with_external_gateway()
    assert result["status"] == "success"

# ✅ Skip tests conditionally
@pytest.mark.skipif(not has_redis(), reason="Redis not available")
def test_redis_caching():
    """Test Redis caching functionality."""
    cache.set("key", "value")
    assert cache.get("key") == "value"

@pytest.mark.skipif(sys.platform == "win32", reason="Unix-only test")
def test_unix_signals():
    """Test Unix signal handling."""
    handle_signal(signal.SIGTERM)

# Run specific test categories:
# pytest -m "not slow"           # Skip slow tests
# pytest -m "integration"        # Run only integration tests
# pytest -m "slow and not ci"    # Run slow tests not in CI
```

### Parameterized Tests
```python
# ✅ Test multiple scenarios
@pytest.mark.parametrize("username,email,expected_valid", [
    ("validuser", "valid@example.com", True),
    ("", "valid@example.com", False),  # Empty username
    ("validuser", "invalid-email", False),  # Invalid email
    ("user@name", "valid@example.com", False),  # Invalid username chars
    ("toolongusername" * 10, "valid@example.com", False),  # Too long
])
def test_user_validation(username, email, expected_valid):
    """Test user validation with various inputs."""
    user = User(username=username, email=email)
    is_valid = user.is_valid()
    assert is_valid == expected_valid

@pytest.mark.parametrize("role,resource,expected_access", [
    ("admin", "users", True),
    ("admin", "settings", True),
    ("user", "users", False),
    ("user", "profile", True),
    ("guest", "users", False),
    ("guest", "public", True),
])
def test_access_control(role, resource, expected_access):
    """Test role-based access control."""
    user = User(role=role)
    has_access = user.can_access(resource)
    assert has_access == expected_access
```

## 📊 Test Coverage and Quality

### Coverage Configuration
```python
# ✅ Set coverage targets and exclusions
# In pyproject.toml
[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/migrations/*", 
    "*/settings/*",
    "*/__pycache__/*",
]

[tool.coverage.report]
skip_covered = true
skip_empty = true
show_missing = true
precision = 2
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]

# ✅ Branch coverage
[tool.coverage.html]
directory = "htmlcov"

[tool.coverage.xml]
output = "coverage.xml"
```

### Quality Metrics
```python
# ✅ Test quality indicators
def test_edge_cases():
    """Test handles edge cases properly."""
    # Test empty input
    assert process_data([]) == []
    
    # Test single item
    assert process_data([1]) == [1]
    
    # Test maximum size
    large_input = list(range(10000))
    result = process_data(large_input)
    assert len(result) == len(large_input)
    
    # Test invalid input
    with pytest.raises(ValueError):
        process_data(None)

def test_error_conditions():
    """Test error handling comprehensively."""
    # Test specific exception types
    with pytest.raises(ValidationError) as exc_info:
        validate_user_data({"email": "invalid"})
    assert "email" in str(exc_info.value)
    
    # Test error messages
    with pytest.raises(AuthenticationError, match="Invalid credentials"):
        authenticate_user("baduser", "badpass")
```

## 🔧 CI/CD Integration

### GitHub Actions Example
```yaml
# ✅ .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.11, 3.12]
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run tests
      run: |
        pytest --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

## 📋 Testing Checklist

### Unit Tests
- [ ] Test all public methods/functions
- [ ] Test edge cases and boundary conditions
- [ ] Test error conditions and exceptions
- [ ] Use descriptive test names
- [ ] Follow AAA pattern (Arrange, Act, Assert)
- [ ] Mock external dependencies
- [ ] Aim for >90% code coverage

### Integration Tests  
- [ ] Test component interactions
- [ ] Test API endpoints end-to-end
- [ ] Test database operations
- [ ] Test external service integrations
- [ ] Use real or realistic test data

### Performance Tests
- [ ] Test performance-critical paths
- [ ] Set reasonable performance thresholds
- [ ] Test under expected load
- [ ] Monitor memory usage
- [ ] Test concurrency scenarios

### Quality Assurance
- [ ] Tests are fast and reliable
- [ ] Tests are independent and isolated
- [ ] Tests use appropriate fixtures
- [ ] Tests clean up after themselves
- [ ] Tests pass in CI/CD environment
- [ ] Coverage meets project standards 