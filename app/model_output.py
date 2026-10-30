"""Normalize model content across string and content-block API responses."""

from typing import Any


def output_text(content: Any) -> str:
    """Return only user-visible text, excluding reasoning and tool blocks."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            block["text"] for block in content
            if isinstance(block, dict) and block.get("type") in {"text", "output_text"}
            and isinstance(block.get("text"), str)
        ).strip()
    return ""
