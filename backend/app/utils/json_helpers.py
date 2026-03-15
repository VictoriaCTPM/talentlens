"""Shared JSON parsing utilities."""
import json


def parse_llm_json(text: str) -> dict:
    """
    Parse JSON from LLM response, tolerating markdown code fences.
    Used by both analysis engine and document processor.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first line (```json or ```) and last line (```)
        if lines[-1].strip() == "```":
            inner = lines[1:-1]
        else:
            inner = lines[1:]
        text = "\n".join(inner).strip()
    return json.loads(text)
