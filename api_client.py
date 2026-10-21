"""DeepSeek V4.1 Flash API helpers used by the independent Harness window."""

from __future__ import annotations

import json
import logging
import ssl
from typing import Iterable

import httpx
from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)

MODEL_DISPLAY_NAME = "DeepSeek V4.1 Flash"
MODEL_ID = "deepseek-flash"
DEFAULT_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"

SYSTEM_PROMPT = """你是“牢周”，用户的桌面宠物。
你穿绿色运动服、戴耳机和黑框眼镜，总是一副没睡醒、嫌麻烦的样子，但其实很关心用户。
说话像熟悉的朋友：简短、自然、偶尔懒懒地吐槽，不要油腻，也不要每句都硬塞口头禅。
用户问技术问题时要认真、准确、可操作；代码用 Markdown 代码块。回答通常控制在 300 字以内，除非用户明确要求展开。
"""


def normalize_endpoint(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return DEFAULT_ENDPOINT
    if not url.startswith(("http://", "https://")):
        raise ValueError("接口地址需要以 http:// 或 https:// 开头")
    url = url.rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/v1"):
        return url + "/chat/completions"
    if url in ("https://api.deepseek.com", "http://api.deepseek.com"):
        return url + "/chat/completions"
    return url


def request_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "User-Agent": "LaozhouDesktopPet/1.0",
    }


def _server_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict):
                return str(error.get("message") or "").strip()
            if isinstance(error, str):
                return error.strip()
            message = data.get("message")
            if message:
                return str(message).strip()
    except Exception:
        pass
    try:
        text = response.text.strip().replace("\n", " ")
        return text[:240]
    except Exception:
        return ""


def friendly_http_error(status: int, detail: str = "") -> str:
    if status == 200:
        base = "DeepSeek 返回了一条错误信息。"
    else:
        hints = {
            400: "请求格式不被 API 接受，请检查模型名称。",
            401: "API Key 无效或已被撤销，请在设置里重新填写。",
            402: "DeepSeek 账户余额不足，请先充值。",
            403: "当前 API Key 没有访问该模型的权限。",
            404: "接口或模型不存在，请检查接口地址和模型名称。",
            422: "请求参数不被 API 接受，请检查设置。",
            429: "请求太频繁了，喘口气再试。",
            500: "DeepSeek 服务器开小差了，请稍后再试。",
            502: "DeepSeek 网关暂时不可用，请稍后再试。",
            503: "DeepSeek 服务繁忙，请稍后再试。",
            504: "DeepSeek 响应超时，请稍后再试。",
        }
        base = hints.get(status, f"API 返回了错误（HTTP {status}）。")
    detail = (detail or "").strip()
    if detail and detail not in base:
        base += f"\n{detail[:220]}"
    return base


def friendly_exception(exc: Exception) -> str:
    if isinstance(exc, httpx.ConnectTimeout):
        return "连接 DeepSeek 超时，请检查网络或代理设置。"
    if isinstance(exc, httpx.ReadTimeout):
        return "等待 DeepSeek 回复超时，请稍后再试。"
    if isinstance(exc, httpx.ConnectError):
        return "连不上 DeepSeek，请检查网络、代理或接口地址。"
    if isinstance(exc, ssl.SSLError):
        return "TLS 证书验证失败，请检查系统时间或网络代理。"
    if isinstance(exc, httpx.HTTPError):
        return f"网络请求失败：{exc}"
    return str(exc) or exc.__class__.__name__


class ValidateThread(QThread):
    ok = Signal(str)
    failed = Signal(str)

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = dict(cfg)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            endpoint = normalize_endpoint(self.cfg.get("base_url", DEFAULT_ENDPOINT))
            payload = {
                "model": self.cfg.get("model") or MODEL_ID,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "stream": False,
            }
            with httpx.Client(timeout=httpx.Timeout(25.0, connect=12.0),
                              follow_redirects=True) as client:
                response = client.post(endpoint,
                                       headers=request_headers(self.cfg.get("api_key", "")),
                                       json=payload)
            if self._cancelled:
                return
            if 200 <= response.status_code < 300:
                try:
                    data = response.json()
                    model = str((data or {}).get("model") or payload["model"])
                except Exception:
                    model = payload["model"]
                self.ok.emit(model)
            else:
                self.failed.emit(friendly_http_error(response.status_code,
                                                     _server_detail(response)))
        except Exception as exc:
            if not self._cancelled:
                self.failed.emit(friendly_exception(exc))


class ChatThread(QThread):
    chunk = Signal(str)
    completed = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, cfg: dict, messages: Iterable[dict], parent=None):
        super().__init__(parent)
        self.cfg = dict(cfg)
        self.messages = list(messages)
        self._cancelled = False
        self._response: httpx.Response | None = None

    def cancel(self) -> None:
        self._cancelled = True
        response = self._response
        if response is not None:
            try:
                response.close()
            except Exception:
                pass

    def run(self) -> None:
        full: list[str] = []
        try:
            endpoint = normalize_endpoint(self.cfg.get("base_url", DEFAULT_ENDPOINT))
            payload = {
                "model": self.cfg.get("model") or MODEL_ID,
                "messages": self.messages,
                "stream": True,
                "temperature": 0.65,
                "max_tokens": 1400,
            }
            timeout = httpx.Timeout(90.0, connect=15.0, read=90.0)
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                with client.stream(
                    "POST", endpoint,
                    headers=request_headers(self.cfg.get("api_key", "")),
                    json=payload,
                ) as response:
                    self._response = response
                    if response.status_code < 200 or response.status_code >= 300:
                        response.read()
                        self.failed.emit(friendly_http_error(
                            response.status_code, _server_detail(response)
                        ))
                        return

                    content_type = response.headers.get("content-type", "")
                    if "text/event-stream" not in content_type.lower():
                        # Some compatible gateways ignore stream=True.  Accept a
                        # regular JSON completion too.
                        response.read()
                        try:
                            data = response.json()
                            text = data["choices"][0]["message"]["content"]
                        except Exception:
                            self.failed.emit("API 返回了无法识别的数据格式。")
                            return
                        if text:
                            full.append(str(text))
                            self.chunk.emit(str(text))
                        if not self._cancelled:
                            self.completed.emit("".join(full))
                        else:
                            self.cancelled.emit()
                        return

                    for line in response.iter_lines():
                        if self._cancelled:
                            break
                        if not line:
                            continue
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data_text = line[5:].strip()
                        if not data_text or data_text == "[DONE]":
                            if data_text == "[DONE]":
                                break
                            continue
                        try:
                            obj = json.loads(data_text)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(obj, dict) and obj.get("error"):
                            self.failed.emit(friendly_http_error(200,
                                                                 str(obj["error"])))
                            return
                        try:
                            delta = obj["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                        except (KeyError, IndexError, TypeError):
                            continue
                        if isinstance(content, list):
                            content = "".join(
                                part.get("text", "") for part in content
                                if isinstance(part, dict)
                            )
                        if content:
                            text = str(content)
                            full.append(text)
                            self.chunk.emit(text)

            if self._cancelled:
                self.cancelled.emit()
            elif full:
                self.completed.emit("".join(full))
            else:
                self.failed.emit("DeepSeek 没有返回文字内容，请再试一次。")
        except Exception as exc:
            if self._cancelled:
                self.cancelled.emit()
            else:
                log.exception("Chat request failed")
                self.failed.emit(friendly_exception(exc))
        finally:
            self._response = None
