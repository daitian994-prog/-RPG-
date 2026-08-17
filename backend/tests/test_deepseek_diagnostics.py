import unittest
from unittest.mock import MagicMock, patch

import httpx

from backend.services.deepseek_service import DeepSeekError, DeepSeekService


class DummyRepository:
    node = {
        "id": "diagnostic-node", "name": "test", "provider": "deepseek",
        "base_url": "https://example.invalid", "model": "test-model",
        "api_key": "secret", "enabled": True,
    }

    def active(self, *, include_secret=False):
        if include_secret:
            return dict(self.node)
        return {key: value for key, value in self.node.items() if key != "api_key"}

    @staticmethod
    def public(value):
        return {key: item for key, item in value.items() if key != "api_key"}


class DeepSeekDiagnosticTest(unittest.TestCase):
    def setUp(self):
        DeepSeekService._node_errors.clear()
        self.service = DeepSeekService(DummyRepository())

    @patch("backend.services.deepseek_service.httpx.Client")
    def test_connect_error_is_safe_and_shared_with_admin_status(self, client_type):
        client = client_type.return_value.__enter__.return_value
        client.post.side_effect = httpx.ConnectError("secret transport details")
        with self.assertRaisesRegex(DeepSeekError, "API 连接失败"):
            self.service.generate(system="test", prompt="test")
        status = DeepSeekService(DummyRepository()).status()
        self.assertEqual(status["last_error"]["type"], "ConnectError")
        self.assertNotIn("secret transport details", str(status["last_error"]))

    @patch("backend.services.deepseek_service.httpx.Client")
    def test_invalid_response_shape_has_distinct_diagnostic(self, client_type):
        response = MagicMock()
        response.json.return_value = {"unexpected": True}
        client_type.return_value.__enter__.return_value.post.return_value = response
        with self.assertRaisesRegex(DeepSeekError, "返回格式无法解析"):
            self.service.generate(system="test", prompt="test")
        self.assertEqual(self.service.status()["last_error"]["type"], "InvalidResponse")


if __name__ == "__main__":
    unittest.main()
