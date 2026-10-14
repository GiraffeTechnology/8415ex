"""Refusal codes. Every rejection names one, so a caller can act on it."""


class DomainError(Exception):
    """A refused operation. ``code`` is stable; the message is for humans."""

    def __init__(self, code, detail=None):
        if not isinstance(code, str) or not code:
            raise ValueError("a refusal needs a code")
        super().__init__(code if detail is None else f"{code}: {detail}")
        self.code = code
        self.detail = detail


def require(condition, code, detail=None):
    """Refuse with ``code`` unless ``condition`` holds."""
    if not condition:
        raise DomainError(code, detail)
