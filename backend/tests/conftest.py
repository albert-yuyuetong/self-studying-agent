"""Tests never inherit a developer's paid model or production database settings."""

import atexit
import os
import tempfile


_test_data = tempfile.TemporaryDirectory(prefix="tutor-tests-")
atexit.register(_test_data.cleanup)
os.environ.update({
    "LLM_ENABLED": "false",
    "LLM_API_KEY": "test-only-key",
    "LLM_MODEL": "test-only-model",
    "LLM_BASE_URL": "https://model.example.test/v1",
    "LLM_VERIFY_MODEL": "",
    "LLM_VISION_ENABLED": "false",
    "DATABASE_PATH": os.path.join(_test_data.name, "app.sqlite3"),
})
