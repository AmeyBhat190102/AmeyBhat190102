import json
import pytest

from app import brain, config, policy


# ---------------- JSON extraction ----------------
def test_plain_json():
    assert brain._extract_json('{"a": 1}') == {"a": 1}


def test_fenced_json():
    assert brain._extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_json_with_prose_around_it():
    assert brain._extract_json('Sure, here you go:\n{"a": {"b": 2}}\nHope that helps!') == {"a": {"b": 2}}


def test_braces_inside_strings():
    assert brain._extract_json('{"body": "use {curly} braces :)"}') == {"body": "use {curly} braces :)"}


def test_escaped_quotes():
    assert brain._extract_json('{"body": "she said \\"yes\\""}') == {"body": 'she said "yes"'}


def test_no_json_raises():
    with pytest.raises(ValueError):
        brain._extract_json("no json here at all")


# ---------------- dry-run mock is pipeline-compatible ----------------
def _lead():
    return {"id": "x", "segment": "trek_operator", "name": "Priya", "role": "Founder",
            "company": "Summit Treks", "state": "ENGAGED", "facts": {"research": "runs treks"},
            "summary": ""}


def test_mock_classify_pricing_wins():
    out = brain.classify(_lead(), [], "Love it — what would this cost per poster?")
    assert out["intent"] == "PRICING"


def test_mock_draft_passes_the_policy_wall():
    out = brain.draft(_lead(), [], "opener")
    assert out["channel"] in ("email", "whatsapp")
    assert policy.check_content(out["body"]).ok
    assert config.SIGNATURE in out["body"]
    assert "no thanks" in out["body"]          # opt-out line present


def test_mock_critic_ok():
    assert brain.critic(_lead(), "clean body", "opener")["ok"] is True


def test_mock_score_shape():
    out = brain.score_lead("trek_operator", _lead())
    assert 0 <= out["score"] <= 100 and isinstance(out["flags"], list)
