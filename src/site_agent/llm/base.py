"""The one interface every model backend implements, plus the HTTP call and error handling they share."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


class LLMError(Exception):
    """The model server could not be reached, or it returned something the agent cannot use."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Message:
    role: str  # "system", "user" or "assistant"
    content: str


class ChatClient(Protocol):
    def chat(self, messages: list[Message], *, json_mode: bool = False) -> str:
        """Returns the model's reply as text. json_mode asks the server to return a JSON object where it can."""
        ...


def post_json(url: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise LLMError(f"the server answered HTTP {exc.code}: {detail}", status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"could not reach the model server at {url} ({exc.reason}). Is it running?") from exc
    except TimeoutError as exc:
        raise LLMError(f"the model did not answer within {timeout_s:.0f} seconds. Try a smaller model.") from exc
    except json.JSONDecodeError as exc:
        raise LLMError(f"the server's reply was not JSON: {exc}") from exc
