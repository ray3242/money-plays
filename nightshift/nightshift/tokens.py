"""Token accounting.

Every string that enters an agent's context (prompt, tool output, recalled memory) is counted
with the same function in every mode, so cold-vs-Meko comparisons are apples to apples.
Uses tiktoken when installed, otherwise the usual ~4 characters per token estimate.
"""
import math

try:  # optional
    import tiktoken

    _enc = tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover - depends on environment
    _enc = None

METHOD = "tiktoken/cl100k_base" if _enc else "chars/4 estimate"


def count(text) -> int:
    if not text:
        return 0
    if not isinstance(text, str):
        text = str(text)
    if _enc:
        return len(_enc.encode(text))
    return math.ceil(len(text) / 4)
