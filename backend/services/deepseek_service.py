import os
import json
from collections.abc import Iterator
from typing import Any

import httpx

from backend.database.api_nodes import ApiNodeRepository


class DeepSeekError(RuntimeError):
    pass


class DeepSeekService:
    """Server-only OpenAI-compatible client with a SQLite active-node selector."""

    _node_errors: dict[str, dict[str, Any]] = {}

    def __init__(self, repository: ApiNodeRepository | None = None) -> None:
        self.repository = repository or ApiNodeRepository()
        # Narrative calls must never leave the player staring at a blocked event screen.
        self.timeout = float(os.getenv("DEEPSEEK_TIMEOUT", "15"))
        self.last_error: str | None = None

    def _environment_config(self) -> dict[str, Any] | None:
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            return None
        return {
            "id": "environment",
            "name": "环境变量",
            "provider": "deepseek",
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip(),
            "api_key": api_key,
            "enabled": True,
        }

    def config(self) -> dict[str, Any] | None:
        return self.repository.active(include_secret=True) or self._environment_config()

    @property
    def configured(self) -> bool:
        return self.config() is not None

    def status(self) -> dict[str, Any]:
        config = self.config()
        shared_error = self._node_errors.get(str(config.get("id"))) if config else None
        return {
            "configured": bool(config),
            "source": "database" if config and config["id"] != "environment" else "environment" if config else None,
            "active_node": self.repository.public(config) if config and config["id"] != "environment" else (
                {
                    "id": "environment",
                    "name": "环境变量",
                    "provider": config["provider"],
                    "base_url": config["base_url"],
                    "model": config["model"],
                    "enabled": True,
                    "has_key": True,
                    "key_mask": "••••••••",
                } if config else None
            ),
            "last_error": shared_error or self.last_error,
            "timeout_seconds": self.timeout,
            "key_exposed": False,
        }

    def _record_error(self, selected: dict[str, Any], error_type: str, message: str, *, http_status: int | None = None) -> None:
        self.last_error = error_type
        diagnostic = {"type": error_type, "message": message, "nodeId": selected.get("id"), "model": selected.get("model")}
        if http_status is not None:
            diagnostic["httpStatus"] = http_status
        self._node_errors[str(selected.get("id"))] = diagnostic

    def _clear_error(self, selected: dict[str, Any]) -> None:
        self.last_error = None
        self._node_errors.pop(str(selected.get("id")), None)

    def generate(
        self,
        *,
        system: str,
        prompt: str,
        temperature: float = 0.8,
        max_tokens: int = 900,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        selected = config or self.config()
        if not selected:
            raise DeepSeekError("尚未启用任何 API 节点。")

        payload: dict[str, Any] = {
            "model": selected["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": max(0, min(2, temperature)),
            "max_tokens": max(64, min(4000, max_tokens)),
            "stream": False,
        }
        if selected.get("provider") == "deepseek":
            payload["thinking"] = {"type": "disabled"}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{selected['base_url'].rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {selected['api_key']}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
            data = response.json()
            result_text = data["choices"][0]["message"]["content"].strip()
            if not result_text:
                self._record_error(selected, "EmptyResponse", "AI 节点返回了空内容。")
                raise DeepSeekError("API 返回了空内容。")
            self._clear_error(selected)
            return {
                "text": result_text,
                "model": data.get("model", selected["model"]),
                "usage": data.get("usage", {}),
                "provider": selected.get("provider", "openai_compatible"),
                "node_id": selected.get("id"),
                "node_name": selected.get("name"),
            }
        except DeepSeekError:
            raise
        except httpx.HTTPStatusError as exc:
            self._record_error(selected, "HTTPStatusError", f"AI 节点返回 HTTP {exc.response.status_code}。", http_status=exc.response.status_code)
            raise DeepSeekError(f"API 请求失败：HTTP {exc.response.status_code}") from exc
        except httpx.ConnectError as exc:
            self._record_error(selected, "ConnectError", "无法连接 AI 节点，请检查本机网络、代理或节点地址。")
            raise DeepSeekError("API 连接失败，请检查网络、代理或节点地址。") from exc
        except httpx.TimeoutException as exc:
            self._record_error(selected, "Timeout", f"AI 节点在 {self.timeout:g} 秒内没有响应。")
            raise DeepSeekError("API 请求超时。") from exc
        except httpx.HTTPError as exc:
            self._record_error(selected, exc.__class__.__name__, "AI 节点发生网络传输错误。")
            raise DeepSeekError("API 网络传输失败。") from exc
        except (KeyError, ValueError, TypeError) as exc:
            self._record_error(selected, "InvalidResponse", "AI 节点返回的数据结构无法解析。")
            raise DeepSeekError("API 返回格式无法解析。") from exc

    def stream(
        self,
        *,
        system: str,
        prompt: str,
        temperature: float = 0.8,
        max_tokens: int = 900,
    ) -> Iterator[str]:
        """Yield text deltas from an OpenAI-compatible SSE response."""
        selected = self.config()
        if not selected:
            raise DeepSeekError("尚未启用任何 API 节点。")
        payload: dict[str, Any] = {
            "model": selected["model"],
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": max(0, min(2, temperature)),
            "max_tokens": max(64, min(4000, max_tokens)),
            "stream": True,
        }
        if selected.get("provider") == "deepseek":
            payload["thinking"] = {"type": "disabled"}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream(
                    "POST",
                    f"{selected['base_url'].rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {selected['api_key']}", "Content-Type": "application/json"},
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            yield delta
            self._clear_error(selected)
        except (httpx.HTTPError, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self._record_error(selected, exc.__class__.__name__, "AI 流式响应连接或解析失败。")
            raise DeepSeekError("API 流式请求失败，远端错误详情已隐藏。") from exc
