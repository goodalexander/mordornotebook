from mordornotebook.redaction import redact_text, redaction_report


def test_redacts_key_like_text():
    text = "OPENAI_API_KEY = 'sk-abcdefghijklmnopqrstuvwxyz1234567890'"
    redacted = redact_text(text)
    assert "sk-" not in redacted
    assert "[REDACTED]" in redacted
    assert redaction_report(text)
