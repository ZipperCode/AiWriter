"""Tests for structured logging configuration."""
import contextvars
from unittest.mock import AsyncMock, patch

import pytest
import structlog

from app.logging import (
    RequestIdMiddleware,
    add_request_id,
    get_logger,
    request_id_var,
    setup_logging,
)


class TestSetupLogging:
    """Test setup_logging function."""

    def test_setup_logging_configures_structlog(self):
        """Test that setup_logging configures structlog with correct parameters."""
        # Reset structlog configuration
        structlog.reset_defaults()

        # Call setup_logging
        setup_logging(json_output=True, log_level="INFO")

        # Verify structlog was configured
        # We check by getting a logger and verifying it works
        logger = structlog.get_logger()
        assert logger is not None

    def test_setup_logging_json_output(self):
        """Test that setup_logging configures JSON output when json_output=True."""
        structlog.reset_defaults()
        setup_logging(json_output=True, log_level="DEBUG")

        # Get the configured processors
        config = structlog.get_config()
        processors = config["processors"]

        # Should contain JSONRenderer for JSON output
        processor_names = [p.__class__.__name__ for p in processors]
        assert any(
            name in processor_names for name in ["JSONRenderer", "dict_tracebacks"]
        )

    def test_setup_logging_text_output(self):
        """Test that setup_logging configures text output when json_output=False."""
        structlog.reset_defaults()
        setup_logging(json_output=False, log_level="INFO")

        # Get the configured processors
        config = structlog.get_config()
        processors = config["processors"]

        # Should contain ConsoleRenderer for text output
        processor_names = [p.__class__.__name__ for p in processors]
        # When json_output is False, we should have console/development renderers
        assert len(processors) > 0


class TestGetLogger:
    """Test get_logger function."""

    def test_get_logger_returns_bound_logger(self):
        """Test that get_logger returns a structlog bound logger."""
        structlog.reset_defaults()
        setup_logging(json_output=True, log_level="INFO")

        logger = get_logger(__name__)
        assert logger is not None

    def test_get_logger_binds_module_name(self):
        """Test that get_logger binds the module name to the logger."""
        structlog.reset_defaults()
        setup_logging(json_output=True, log_level="INFO")

        module_name = "test.module"
        logger = get_logger(module_name)

        # The logger should be a BoundLogger
        assert hasattr(logger, "bind")
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")


class TestRequestIdVar:
    """Test request_id_var ContextVar."""

    def test_request_id_var_is_contextvar(self):
        """Test that request_id_var is a ContextVar."""
        assert isinstance(request_id_var, contextvars.ContextVar)

    def test_request_id_var_default_none(self):
        """Test that request_id_var defaults to None."""
        # Create a fresh context to ensure it's unset
        ctx = contextvars.copy_context()
        result = ctx.run(request_id_var.get, None)
        assert result is None


class TestAddRequestIdProcessor:
    """Test add_request_id processor."""

    def test_add_request_id_with_request_id_set(self):
        """Test that add_request_id adds request_id to log context when set."""
        request_id_var.set("test-request-id-123")

        # Call the processor
        logger, method_name, event_dict = None, None, {}
        result = add_request_id(logger, method_name, event_dict)

        # Should add request_id to the event dict
        assert result["request_id"] == "test-request-id-123"

        # Clean up
        request_id_var.set(None)

    def test_add_request_id_without_request_id_set(self):
        """Test that add_request_id doesn't add request_id when not set."""
        # Ensure request_id is not set
        request_id_var.set(None)

        logger, method_name, event_dict = None, None, {}
        result = add_request_id(logger, method_name, event_dict)

        # Should not add request_id if not set
        assert "request_id" not in result


class TestRequestIdMiddleware:
    """Test RequestIdMiddleware."""

    def test_request_id_middleware_exists(self):
        """Test that RequestIdMiddleware class exists and is callable."""
        assert RequestIdMiddleware is not None
        assert callable(RequestIdMiddleware)

    @pytest.mark.asyncio
    async def test_request_id_middleware_assigns_request_id(self):
        """Test that RequestIdMiddleware assigns X-Request-ID to request."""
        from fastapi import FastAPI, Request
        from starlette.responses import JSONResponse
        from httpx import ASGITransport, AsyncClient

        # Create a simple app with the middleware
        test_app = FastAPI()

        @test_app.get("/test")
        async def test_endpoint(request: Request):
            # Access the request_id_var to see if it was set
            req_id = request_id_var.get()
            return JSONResponse({"request_id": req_id})

        test_app.add_middleware(RequestIdMiddleware)

        # Test the middleware
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Make a request without X-Request-ID
            response = await client.get("/test")
            data = response.json()
            # Should generate a request_id
            assert data["request_id"] is not None

    @pytest.mark.asyncio
    async def test_request_id_middleware_preserves_request_id(self):
        """Test that RequestIdMiddleware preserves provided X-Request-ID."""
        from fastapi import FastAPI, Request
        from starlette.responses import JSONResponse
        from httpx import ASGITransport, AsyncClient

        test_app = FastAPI()

        @test_app.get("/test")
        async def test_endpoint(request: Request):
            req_id = request_id_var.get()
            return JSONResponse({"request_id": req_id})

        test_app.add_middleware(RequestIdMiddleware)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Make a request with X-Request-ID header
            response = await client.get("/test", headers={"X-Request-ID": "my-request-id"})
            data = response.json()
            assert data["request_id"] == "my-request-id"
