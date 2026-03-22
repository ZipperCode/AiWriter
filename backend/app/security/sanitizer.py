"""Prompt injection sanitization utilities."""

import re
from typing import List

# Compiled regex patterns for detecting prompt injection attempts
INJECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a\s+", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(your\s+)?(previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?prior", re.IGNORECASE),
    re.compile(r"new\s+system\s+prompt", re.IGNORECASE),
    re.compile(r"override\s+(system|instructions)", re.IGNORECASE),
]

# Compiled regex patterns for content to strip from text
STRIP_PATTERNS: List[re.Pattern] = [
    # Markdown role markers: ## System, ## Assistant, ## User, etc.
    re.compile(r"##\s+(System|Assistant|User|Prompt|Instruction)", re.IGNORECASE),
    # XML-like injection tags: <system>...</system>, <assistant>...</assistant>, etc.
    re.compile(
        r"<(system|assistant|prompt|instruction)>.*?</(system|assistant|prompt|instruction)>",
        re.IGNORECASE | re.DOTALL,
    ),
    # Self-closing XML-like tags: <system/>, <instruction/>, etc.
    re.compile(r"<(system|assistant|prompt|instruction)\s*/?>", re.IGNORECASE),
]


def detect_injection(text: str) -> bool:
    """Check if text contains prompt injection attempts.

    Args:
        text: The text to check for injection patterns.

    Returns:
        bool: True if any injection pattern is detected, False otherwise.
    """
    if not text:
        return False
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def sanitize_for_prompt(text: str) -> str:
    """Remove prompt injection patterns and role markers from text.

    This function:
    1. Removes detected injection patterns and role markers
    2. Strips XML-like injection tags
    3. Normalizes whitespace
    4. Returns the cleaned text

    Normal narrative text passes through unchanged (except for whitespace normalization).

    Args:
        text: The text to sanitize for safe use in LLM prompts.

    Returns:
        str: The sanitized text with injection patterns removed and whitespace normalized.
    """
    if not text:
        return ""

    result = text

    # Apply strip patterns to remove injection attempts and role markers
    for pattern in STRIP_PATTERNS:
        result = pattern.sub("", result)

    # Remove injection patterns
    for pattern in INJECTION_PATTERNS:
        result = pattern.sub("", result)

    # Normalize whitespace: collapse multiple spaces, tabs, newlines
    result = re.sub(r"\s+", " ", result)

    # Strip leading and trailing whitespace
    result = result.strip()

    return result
