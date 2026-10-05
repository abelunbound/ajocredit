"""
test_api_startup.py

Tests for api.py startup validation.
Ensures the application fails fast with clear errors for invalid JWT secrets.

Run with: pytest test_api_startup.py -v
"""

import os
import sys
import subprocess
import pytest


INSECURE_PLACEHOLDER = "your-super-secret-jwt-key-change-this-to-something-random-and-secure"


def run_api_startup(env_vars, unset=()):
    """
    Attempt to start api.py with given environment variables.
    Returns (exit_code, stderr_output).
    """
    env = os.environ.copy()
    env.update(env_vars)
    for name in unset:
        env.pop(name, None)
    
    # Try to import and execute the module-level code
    # We use subprocess to isolate the sys.exit() calls
    result = subprocess.run(
        [sys.executable, "-c", "import api"],
        env=env,
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    return result.returncode, result.stderr


def test_missing_jwt_secret():
    """Test that startup fails when JWT_SECRET_KEY is not set."""
    env = {
        "DATABASE_URL": "postgresql://test:test@localhost/test"
    }
    exit_code, stderr = run_api_startup(env, unset=("JWT_SECRET_KEY",))
    
    assert exit_code == 1, "Should exit with code 1 when JWT_SECRET_KEY is missing"
    assert "JWT_SECRET_KEY environment variable is required but not set" in stderr
    assert "at least 32 characters" in stderr


def test_jwt_secret_too_short():
    """Test that startup fails when JWT_SECRET_KEY is shorter than 32 characters."""
    env = {
            "JWT_SECRET_KEY": "short-key-only-25-chars!!",  # 25 characters
        "DATABASE_URL": "postgresql://test:test@localhost/test"
    }
    
    exit_code, stderr = run_api_startup(env)
    
    assert exit_code == 1, "Should exit with code 1 when JWT_SECRET_KEY is too short"
    assert "must be at least 32 characters long" in stderr
    assert "got 25" in stderr


def test_jwt_secret_is_placeholder():
    """Test that startup fails when JWT_SECRET_KEY equals the insecure placeholder."""
    env = {
        "JWT_SECRET_KEY": INSECURE_PLACEHOLDER,
        "DATABASE_URL": "postgresql://test:test@localhost/test"
    }
    
    exit_code, stderr = run_api_startup(env)
    
    assert exit_code == 1, "Should exit with code 1 when JWT_SECRET_KEY is the placeholder"
    assert "insecure placeholder value" in stderr
    assert "NEVER use the example placeholder" in stderr


def test_valid_jwt_secret():
    """Test that startup succeeds with a valid JWT_SECRET_KEY (at module import level)."""
    # This test verifies the validation passes with a valid key
    # Note: Full app startup will still fail without database.py, but validation should pass
    env = {
        "JWT_SECRET_KEY": "a" * 32,  # Exactly 32 characters (minimum valid)
        "DATABASE_URL": "postgresql://test:test@localhost/test"
    }
    
    exit_code, stderr = run_api_startup(env)
    
    # The import will fail due to missing database.py, but not due to JWT validation
    # Check that our specific JWT validation errors are NOT present
    assert "JWT_SECRET_KEY environment variable is required but not set" not in stderr
    assert "must be at least 32 characters long" not in stderr
    assert "insecure placeholder value" not in stderr


if __name__ == "__main__":
    # Allow running directly for quick testing
    pytest.main([__file__, "-v"])
