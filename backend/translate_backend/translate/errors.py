"""Classified service errors (no request or response content). Kept apart from http.py so that importing the
pipeline does not load http.client/ssl until the first service call."""


class HttpError(Exception):
    def __init__(self, kind: str, status: int = 0, retry_after: float = 0.0, detail: str = ""):
        super().__init__(kind)
        self.kind = kind  # network | timeout | auth | rate | http | notFound | badUrl | parse | refused
        self.detail = detail  # the service's own short error text (type/message), for the settings test only
        self.conn = ""  # diagnostics: "new" or "reused <age>s" — the connection the request went out on
        self.status = status
        self.retry_after = retry_after
