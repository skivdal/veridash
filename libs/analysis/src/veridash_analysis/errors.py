"""Expected typed failures raised by analysis kernels."""

from veridash_core import ErrorKind


class AnalysisExecutionError(Exception):
    """A classified kernel failure safe for the wrapper to translate."""

    def __init__(
        self,
        *,
        kind: ErrorKind,
        public_message: str,
        retryable: bool,
        diagnostic: str | None = None,
    ) -> None:
        super().__init__(public_message)
        self.kind = kind
        self.public_message = public_message
        self.retryable = retryable
        self.diagnostic = diagnostic
