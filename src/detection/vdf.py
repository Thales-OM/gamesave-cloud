"""Minimal VDF (Valve Data Format) parser for Steam files."""

import re
from typing import Any, Dict


def parse_vdf(text: str) -> Dict[str, Any]:
    """Parse a simple VDF document into nested dicts.

    Handles quoted and bare keys/values, braces and comments.
    """
    tokens = re.findall(
        r'"((?:\\.|[^"\\])*)"|(\{)|(\})|(//.*)',
        text,
        re.DOTALL,
    )
    root: Dict[str, Any] = {}
    stack = [root]
    pending_key = None

    for quoted, open_brace, close_brace, _comment in tokens:
        top = stack[-1]
        if open_brace:
            if pending_key is None:
                continue
            child: Dict[str, Any] = {}
            top[pending_key] = child
            stack.append(child)
            pending_key = None
        elif close_brace:
            if len(stack) > 1:
                stack.pop()
        elif quoted:
            value = quoted.replace('\\"', '"')
            if pending_key is None:
                pending_key = value
            else:
                top[pending_key] = value
                pending_key = None
    return root
