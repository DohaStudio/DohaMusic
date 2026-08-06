"""Provider-private failures that never cross the adapter boundary."""


class OpenAIProviderError(Exception):
    def __init__(self, kind: str, *, retryable: bool = False) -> None:
        super().__init__(kind)
        self.kind = kind
        self.retryable = retryable
