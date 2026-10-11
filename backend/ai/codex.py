"""ChatGPT Codex Responses API adapter used when a Plus/Pro subscription is signed in."""

from __future__ import annotations

import json
from typing import Any

import httpx

from backend.ai.oauth.chatgpt import (
    CHATGPT_CLIENT_VERSION,
    CHATGPT_CODEX_URL,
    USER_AGENT,
)
from backend.ai.oauth.runtime import chatgpt_oauth

DEFAULT_CODEX_MODEL = "gpt-5.5"


class ChatResult:
    type = "ai"

    def __init__(self, content: str = "", tool_calls: list | None = None):
        self.content = content
        self.tool_calls = tool_calls or []


class CodexChatModel:
    def __init__(
        self,
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list | None = None,
    ):
        self.model = model or DEFAULT_CODEX_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tools = tools or []
        self.http = httpx.Client(timeout=120.0)

    def bind_tools(self, tools: list):
        return CodexChatModel(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=tools,
        )

    def invoke(self, messages: list):
        payload_input, instructions = langchain_messages_to_codex_input(messages)
        body: dict[str, Any] = {
            "model": self.model,
            "input": payload_input,
            "store": False,
            "stream": True,
        }
        if instructions.strip():
            body["instructions"] = instructions
        specs = [codex_tool_spec(tool) for tool in self.tools]
        specs = [item for item in specs if item]
        if specs:
            body["tools"] = specs

        token = chatgpt_oauth.bearer()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": USER_AGENT,
            "originator": "codex_cli_rs",
            "openai-beta": "responses=v1",
            "ChatGPT-Client-Version": CHATGPT_CLIENT_VERSION,
        }
        account_id = chatgpt_oauth.account_id()
        if account_id:
            headers["ChatGPT-Account-Id"] = account_id

        response = self.http.post(CHATGPT_CODEX_URL, json=body, headers=headers)
        if response.status_code >= 400:
            raise ValueError(
                f"ChatGPT Codex error (HTTP {response.status_code}): {response.text[:400]}"
            )

        content_type = response.headers.get("content-type", "")
        if content_type.startswith("text/event-stream") or response.status_code < 300:
            data = collapse_responses_stream(response.text)
        else:
            data = response.json()

        error = (data or {}).get("error")
        if isinstance(error, dict) and error.get("message"):
            raise ValueError(str(error["message"]))

        return parse_codex_result(data or {})


def langchain_messages_to_codex_input(messages: list) -> tuple[list[dict], str]:
    items: list[dict] = []
    instructions: list[str] = []
    for message in messages:
        role = getattr(message, "type", None) or getattr(message, "role", "")
        text = _message_text(message)
        if role == "system":
            if text.strip():
                instructions.append(text)
            continue
        if role in {"human", "user"}:
            items.append({"role": "user", "content": text})
            continue
        if role in {"ai", "assistant"}:
            if text.strip():
                items.append({"role": "assistant", "content": text})
            for call in getattr(message, "tool_calls", None) or []:
                args = call.get("args") if isinstance(call, dict) else {}
                items.append(
                    {
                        "type": "function_call",
                        "call_id": (call.get("id") if isinstance(call, dict) else "")
                        or "",
                        "name": call.get("name") if isinstance(call, dict) else "",
                        "arguments": args
                        if isinstance(args, str)
                        else json.dumps(args or {}),
                    }
                )
            continue
        if role == "tool":
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": getattr(message, "tool_call_id", "") or "",
                    "output": text,
                }
            )
    return items, "\n\n".join(instructions)


def codex_tool_spec(tool) -> dict | None:
    name = getattr(tool, "name", "")
    if not name:
        return None
    schema = {"type": "object", "properties": {}}
    args_schema = getattr(tool, "args_schema", None)
    if args_schema is not None and hasattr(args_schema, "model_json_schema"):
        schema = args_schema.model_json_schema()
    elif getattr(tool, "args", None):
        schema = {"type": "object", "properties": tool.args}
    return {
        "type": "function",
        "name": name,
        "description": getattr(tool, "description", "") or "",
        "parameters": schema,
    }


def collapse_responses_stream(raw: str) -> dict:
    last: dict | None = None
    completed_items: list = []
    text_parts: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        event_type = str(event.get("type") or "")
        response = event.get("response")
        if event_type.startswith("response.") and isinstance(response, dict):
            last = response
            if event_type in {
                "response.completed",
                "response.incomplete",
                "response.failed",
            }:
                return restore_stream_output(last, completed_items, "".join(text_parts))
        if event_type == "response.output_item.done" and event.get("item"):
            completed_items.append(event["item"])
        if event_type == "response.output_text.delta":
            text_parts.append(str(event.get("delta") or ""))
        if event_type == "response.output_text.done" and event.get("text"):
            text_parts = [str(event.get("text") or "")]
        if event_type == "error" and event.get("error"):
            return {"error": event["error"]}
    if last is not None:
        return restore_stream_output(last, completed_items, "".join(text_parts))
    raise ValueError("The ChatGPT response stream ended without a result")


def restore_stream_output(response: dict, completed_items: list, text: str) -> dict:
    existing = response.get("output")
    if isinstance(existing, list) and existing:
        return response
    patched = dict(response)
    if completed_items:
        patched["output"] = completed_items
    elif text:
        patched["output"] = [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": text}],
            }
        ]
    return patched


def parse_codex_result(data: dict) -> ChatResult:
    texts: list[str] = []
    tool_calls: list[dict] = []
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type") or ""
        if item_type == "function_call":
            arguments = item.get("arguments") or "{}"
            if isinstance(arguments, str):
                try:
                    args = json.loads(arguments)
                except json.JSONDecodeError:
                    args = {"raw": arguments}
            else:
                args = arguments
            tool_calls.append(
                {
                    "id": item.get("call_id") or item.get("id") or "",
                    "name": item.get("name") or "",
                    "args": args if isinstance(args, dict) else {"value": args},
                }
            )
            continue
        if item_type in {"message", ""}:
            content = item.get("content")
            texts.append(_decode_content(content))
    return ChatResult(content="\n".join(part for part in texts if part).strip(), tool_calls=tool_calls)


def _decode_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("output_text") or ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    if content is None:
        return ""
    return str(content)


def _message_text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content or "")
