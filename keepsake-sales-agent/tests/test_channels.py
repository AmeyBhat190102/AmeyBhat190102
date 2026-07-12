from app import channels


def test_tpl_param_strips_newlines_and_runs_of_space():
    dirty = "Hi there,\n\nline two\ttabbed    and    wide spaces\n— Asha"
    clean = channels.tpl_param(dirty)
    assert "\n" not in clean and "\t" not in clean and "  " not in clean
    assert clean.startswith("Hi there, line two")


def test_tpl_param_truncates():
    assert len(channels.tpl_param("word " * 500, limit=100)) <= 100


def test_parse_wa_webhook():
    payload = {"entry": [{"changes": [{"value": {
        "contacts": [{"wa_id": "9198765", "profile": {"name": "Priya"}}],
        "messages": [
            {"type": "text", "from": "9198765", "id": "wamid.ABC", "text": {"body": "hello"}},
            {"type": "image", "from": "9198765", "id": "wamid.DEF"},   # non-text skipped
        ]}}]}]}
    out = channels.parse_wa_webhook(payload)
    assert out == [{"phone": "+9198765", "text": "hello", "name": "Priya", "wamid": "wamid.ABC"}]


def test_parse_smartlead_reply():
    payload = {"event_type": "EMAIL_REPLY", "to_email": "p@summittreks.in",
               "reply_body_plain": "sounds interesting, tell me more",
               "email_stats_id": "s1", "message_id": "<m1@x>", "campaign_id": "c1"}
    out = channels.parse_smartlead_webhook(payload)
    assert out["email"] == "p@summittreks.in"
    assert out["meta"]["stats_id"] == "s1" and out["meta"]["message_id"] == "<m1@x>"


def test_parse_smartlead_ignores_non_reply():
    assert channels.parse_smartlead_webhook({"event_type": "EMAIL_SENT"}) is None
