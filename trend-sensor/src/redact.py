import re

# Credential-carrying query params that Google/Meta client errors embed in
# request URLs (HttpError includes the full URL, key included).
_SECRET_PARAMS = re.compile(r"(key|access_token)=[^&\s\"'<>]+", re.IGNORECASE)


def redact_secrets(text: str) -> str:
    """Strips credential query params (API keys, tokens) from log/error text."""
    return _SECRET_PARAMS.sub(r"\1=REDACTED", text or "")
