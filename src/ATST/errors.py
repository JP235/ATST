class ATSTError(Exception):
    """Base exception for ATST parsing and validation errors."""


class ATSTParseError(ATSTError):
    """Raised when ATST text cannot be parsed."""


class ATSTValidationError(ATSTError):
    """Raised when parsed ATST content violates the format rules."""


class ATSTReservedNameError(ATSTValidationError):
    """Raised when a user-defined identifier uses a reserved name."""

