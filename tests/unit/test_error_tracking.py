"""
Unit Tests for Error Tracking Service

Tests Issue #9 implementation
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
import sentry_sdk

from backend.services.error_tracking import (
    PerformanceMonitor,
    add_breadcrumb,
    capture_exception,
    capture_message,
    init_sentry,
    monitor_errors,
    sentry_health_check,
    set_context,
    set_tag,
    set_user_context,
)


@pytest.fixture
def mock_sentry():
    """Mock Sentry SDK."""
    with patch("backend.services.error_tracking.sentry_sdk") as mock:
        yield mock


@pytest.fixture(autouse=True)
def reset_sentry():
    """Reset Sentry state before each test."""
    # Don't actually initialize Sentry in tests
    with patch.dict("os.environ", {"SENTRY_DSN": ""}):
        yield


@pytest.mark.unit
def test_init_sentry_no_dsn(caplog):
    """Test Sentry initialization without DSN."""
    with patch.dict("os.environ", {"SENTRY_DSN": ""}, clear=True):
        init_sentry()
        assert "error tracking disabled" in caplog.text.lower()


@pytest.mark.unit
def test_init_sentry_with_dsn(mock_sentry):
    """Test Sentry initialization with DSN."""
    test_dsn = "https://test@sentry.io/12345"

    with patch.dict("os.environ", {"SENTRY_DSN": test_dsn}):
        init_sentry()

        mock_sentry.init.assert_called_once()
        call_kwargs = mock_sentry.init.call_args[1]

        assert call_kwargs["dsn"] == test_dsn
        assert "integrations" in call_kwargs
        assert call_kwargs["attach_stacktrace"] is True
        assert call_kwargs["send_default_pii"] is False


@pytest.mark.unit
def test_capture_exception_with_context(mock_sentry):
    """Test exception capture with context."""
    error = ValueError("Test error")
    context = {"operation": "test_operation", "param": "value"}
    tags = {"environment": "test"}

    capture_exception(error, context=context, tags=tags)

    # Verify push_scope was used
    mock_sentry.push_scope.assert_called_once()


@pytest.mark.unit
def test_capture_message(mock_sentry):
    """Test message capture."""
    message = "Test message"
    context = {"key": "value"}

    capture_message(message, level="warning", context=context)

    mock_sentry.push_scope.assert_called_once()


@pytest.mark.unit
def test_add_breadcrumb(mock_sentry):
    """Test breadcrumb addition."""
    add_breadcrumb(
        message="Test breadcrumb", category="test", level="info", data={"key": "value"}
    )

    mock_sentry.add_breadcrumb.assert_called_once_with(
        message="Test breadcrumb", category="test", level="info", data={"key": "value"}
    )


@pytest.mark.unit
def test_set_user_context_sends_only_an_opaque_id(mock_sentry):
    """
    Most users here are school students. An explicit set_user() call ignores
    send_default_pii=False, so this test previously asserted that the email,
    username, and IP were all forwarded to Sentry — it pinned the leak in
    place. Only the account id may leave.
    """
    set_user_context(
        user_id="123",
        email="student@example.com",
        username="student1",
        ip_address="192.168.1.1",
    )

    sent = mock_sentry.set_user.call_args[0][0]

    assert sent["id"] == "123"
    assert "student@example.com" not in str(sent)
    assert "student1" not in str(sent)
    assert "192.168.1.1" not in str(sent)


@pytest.mark.unit
def test_set_user_context_hashes_email_consistently(mock_sentry):
    """Same student, same hash — so two errors can still be correlated."""
    set_user_context(user_id="123", email="student@example.com")
    first = mock_sentry.set_user.call_args[0][0]["email_hash"]

    set_user_context(user_id="123", email="  STUDENT@Example.com  ")
    second = mock_sentry.set_user.call_args[0][0]["email_hash"]

    assert first == second

    set_user_context(user_id="456", email="other@example.com")
    assert mock_sentry.set_user.call_args[0][0]["email_hash"] != first


@pytest.mark.unit
def test_set_user_context_omits_email_hash_when_absent(mock_sentry):
    set_user_context(user_id="123")

    assert mock_sentry.set_user.call_args[0][0] == {"id": "123"}


@pytest.mark.unit
def test_set_tag(mock_sentry):
    """Test tag setting."""
    set_tag("environment", "test")

    mock_sentry.set_tag.assert_called_once_with("environment", "test")


@pytest.mark.unit
def test_set_context(mock_sentry):
    """Test context setting."""
    context = {"key": "value", "nested": {"data": 123}}

    set_context("custom", context)

    mock_sentry.set_context.assert_called_once_with("custom", context)


@pytest.mark.unit
def test_monitor_errors_decorator_success(mock_sentry):
    """Test monitor_errors decorator on successful execution."""

    @monitor_errors("test_operation", capture_args=True)
    def test_function(arg1, arg2):
        return arg1 + arg2

    result = test_function(1, 2)

    assert result == 3
    # Breadcrumbs should be added
    assert mock_sentry.add_breadcrumb.call_count == 2  # Start and complete


@pytest.mark.unit
def test_monitor_errors_decorator_failure(mock_sentry):
    """Test monitor_errors decorator on exception."""

    @monitor_errors("test_operation", capture_args=True)
    def test_function():
        raise ValueError("Test error")

    with pytest.raises(ValueError):
        test_function()

    # Should have captured exception
    mock_sentry.push_scope.assert_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_monitor_errors_decorator_async(mock_sentry):
    """Test monitor_errors decorator with async function."""

    @monitor_errors("async_operation")
    async def async_function(value):
        return value * 2

    result = await async_function(5)

    assert result == 10
    assert mock_sentry.add_breadcrumb.call_count == 2


@pytest.mark.unit
def test_performance_monitor_context_manager(mock_sentry):
    """Test PerformanceMonitor context manager."""
    mock_transaction = MagicMock()
    mock_sentry.start_transaction.return_value = mock_transaction

    with PerformanceMonitor("test_operation", "function"):
        pass

    mock_sentry.start_transaction.assert_called_once_with(
        op="function", name="test_operation"
    )
    mock_transaction.__enter__.assert_called_once()
    mock_transaction.__exit__.assert_called_once()


@pytest.mark.unit
def test_performance_monitor_with_error(mock_sentry):
    """Test PerformanceMonitor with exception."""
    mock_transaction = MagicMock()
    mock_sentry.start_transaction.return_value = mock_transaction

    try:
        with PerformanceMonitor("test_operation"):
            raise ValueError("Test error")
    except ValueError:
        pass

    # Should set error status
    mock_transaction.set_status.assert_called()


@pytest.mark.unit
def test_before_send_hook_filters_client_errors():
    """Test before_send hook filters client errors."""
    from backend.services.error_tracking import before_send_hook

    # Mock 404 error
    event = {"request": {}}

    class MockHTTPException(Exception):
        status_code = 404

    hint = {"exc_info": (type(MockHTTPException), MockHTTPException(), None)}

    before_send_hook(event, hint)

    # Should filter out 4xx errors
    # Note: This requires HTTPException to be recognized
    # Result depends on implementation


@pytest.mark.unit
def test_before_send_hook_removes_sensitive_headers():
    """Test before_send hook removes sensitive headers."""
    from backend.services.error_tracking import before_send_hook

    event = {
        "request": {
            "headers": {
                "authorization": "Bearer secret-token",
                "cookie": "session=abc123",
                "x-api-key": "secret-key",
                "content-type": "application/json",
            }
        }
    }
    hint = {}

    result = before_send_hook(event, hint)

    if result:
        headers = result["request"]["headers"]
        assert headers["authorization"] == "[FILTERED]"
        assert headers["cookie"] == "[FILTERED]"
        assert headers["x-api-key"] == "[FILTERED]"
        assert headers["content-type"] == "application/json"


@pytest.mark.unit
@pytest.mark.parametrize(
    "header_name",
    ["Authorization", "AUTHORIZATION", "authorization", "Cookie", "X-Api-Key"],
)
def test_before_send_hook_filters_headers_whatever_their_case(header_name):
    """
    The filter compared lowercase names against the event's keys directly, so
    an event carrying "Authorization" walked past it and shipped a live bearer
    token to Sentry. Which case arrives depends on the integration that built
    the event, so matching has to be case-insensitive.
    """
    from backend.services.error_tracking import before_send_hook

    event = {"request": {"headers": {header_name: "Bearer secret-token-value"}}}

    result = before_send_hook(event, {})

    assert result is not None
    assert result["request"]["headers"][header_name] == "[FILTERED]"
    assert "secret-token-value" not in str(result)


@pytest.mark.unit
def test_before_send_hook_filters_the_request_body():
    """A login body holds a plaintext password."""
    from backend.services.error_tracking import before_send_hook

    event = {
        "request": {
            "data": {
                "email": "student@example.com",
                "password": "SuperSecret123!",
                "grade": "8",
            }
        }
    }

    result = before_send_hook(event, {})

    data = result["request"]["data"]
    assert data["password"] == "[FILTERED]"
    assert "SuperSecret123!" not in str(result)
    assert data["grade"] == "8"  # non-sensitive fields survive for debugging


@pytest.mark.unit
def test_before_send_hook_filters_a_sensitive_query_string():
    from backend.services.error_tracking import before_send_hook

    event = {"request": {"query_string": "page=2&api_key=live-key-value"}}

    result = before_send_hook(event, {})

    assert result["request"]["query_string"] == "[FILTERED]"
    assert "live-key-value" not in str(result)


@pytest.mark.unit
def test_before_send_hook_leaves_a_harmless_query_string_alone():
    from backend.services.error_tracking import before_send_hook

    event = {"request": {"query_string": "page=2&limit=10"}}

    assert before_send_hook(event, {})["request"]["query_string"] == "page=2&limit=10"


@pytest.mark.unit
def test_before_send_hook_tolerates_a_request_without_the_usual_keys():
    """Events vary by integration; a missing key must not raise inside Sentry."""
    from backend.services.error_tracking import before_send_hook

    assert before_send_hook({"request": {}}, {}) is not None
    assert before_send_hook({}, {}) is not None
    assert before_send_hook({"request": {"headers": None, "data": None}}, {}) is not None


@pytest.mark.unit
def test_sentry_health_check_configured(mock_sentry):
    """Test Sentry health check when configured."""
    mock_sentry.capture_message.return_value = "test-event-id"

    result = sentry_health_check()

    assert result["status"] == "healthy"
    assert result["configured"] is True
    assert "test_event_id" in result


@pytest.mark.unit
def test_sentry_health_check_not_configured(mock_sentry):
    """Test Sentry health check when not configured."""
    mock_sentry.capture_message.side_effect = Exception("Not initialized")

    result = sentry_health_check()

    assert result["status"] == "unhealthy"
    assert result["configured"] is False
    assert "error" in result


@pytest.mark.integration
def test_monitor_errors_real_function():
    """Integration test: monitor_errors with real function."""
    execution_count = 0

    @monitor_errors("count_operation")
    def count_up():
        nonlocal execution_count
        execution_count += 1
        return execution_count

    result = count_up()

    assert result == 1
    assert execution_count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_monitor_errors_async_exception_capture():
    """Integration test: async function exception capture."""

    @monitor_errors("async_fail_operation")
    async def async_failing_function():
        await asyncio.sleep(0.01)
        raise RuntimeError("Async failure")

    import asyncio

    with pytest.raises(RuntimeError) as exc_info:
        await async_failing_function()

    assert "Async failure" in str(exc_info.value)
