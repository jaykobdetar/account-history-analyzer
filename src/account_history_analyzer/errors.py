"""Stable public exceptions and CLI exit-code categories."""


class AHASError(Exception):
    """A documented failure, with a stable machine-readable reason code."""

    exit_code = 3

    def __init__(self, message: str, *, code: str = "analysis_error", location: str = "") -> None:
        self.code = code
        self.location = location
        self.message = message
        super().__init__(f"{location + ': ' if location else ''}{code}: {message}")


class InputError(AHASError):
    """Invalid supplied records, manifest, configuration, or reference."""

    exit_code = 2


class ComputationError(AHASError):
    """Unexpected computation failure; never replaced by an absent score."""

    exit_code = 3


class LimitError(AHASError):
    """A configured resource budget prevents complete requested analysis."""

    exit_code = 4


class IntegrityError(AHASError):
    """An artifact, source identity, or recomputed result does not match."""

    exit_code = 5
