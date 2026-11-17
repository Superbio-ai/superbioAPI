import requests


class SuperbioAPIError(requests.HTTPError):
    """An error response from the Superbio API.

    Subclasses ``requests.HTTPError`` so existing ``except requests.HTTPError``
    handlers keep working. ``code`` and the message come from the response body
    when the API sends them, e.g. ``code="insufficient_credits"`` on a 402.
    """

    def __init__(self, response: requests.Response):
        try:
            body = response.json()
        except ValueError:
            body = None
        self.body = body if isinstance(body, dict) else {}
        self.status_code = response.status_code
        self.code = self.body.get("code")
        detail = self.body.get("message") or self.body.get("detail") or response.reason
        message = f"{response.status_code} {detail}"
        if self.code:
            message += f" ({self.code})"
        super().__init__(message, response=response)
