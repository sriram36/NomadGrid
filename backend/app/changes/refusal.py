"""The one exception a change raises when it cannot be done, and how it is shown to the caller."""
from typing import Optional


class Refusal(Exception):
    def __init__(self, code: str, reason: str, suggestion: Optional[str] = None, options: Optional[list] = None):
        self.code, self.reason, self.suggestion, self.options = code, reason, suggestion, options

    def to_response(self, result: str = "REFUSED") -> dict:
        out: dict = {"result": result, "reason_code": self.code, "reason": self.reason}
        if self.suggestion:
            out["suggestion"] = self.suggestion
        if self.options is not None:
            out["options"] = self.options
        return out
