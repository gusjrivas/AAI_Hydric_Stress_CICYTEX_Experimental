from __future__ import annotations

import math
from collections.abc import Mapping


def resolve_choice_confidence(
    *,
    answer_confidence: object | None,
    probabilities: Mapping[str, object] | None,
    choice: str,
) -> float:
    """Apply Laya's confidence precedence for a typed-choice answer."""
    confidence = answer_confidence
    if confidence is None:
        if not isinstance(probabilities, Mapping):
            raise ValueError("Laya response has no answer confidence")
        confidence = probabilities.get(choice)
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("Laya answer confidence is invalid")
    resolved = float(confidence)
    if not math.isfinite(resolved) or not 0.0 <= resolved <= 1.0:
        raise ValueError("Laya answer confidence must be between 0 and 1")
    return resolved
