from src import redact


def test_redact_secrets_strips_key_and_token_params():
    s = "GET https://g/api?foo=1&key=AIzaSy123&access_token=EAAB123&bar=2 failed"
    out = redact.redact_secrets(s)
    assert "AIzaSy123" not in out
    assert "EAAB123" not in out
    assert "foo=1" in out and "bar=2" in out
    assert "key=REDACTED" in out


def test_redact_secrets_handles_none_and_plain_text():
    assert redact.redact_secrets("") == ""
    assert redact.redact_secrets("no secrets here") == "no secrets here"
