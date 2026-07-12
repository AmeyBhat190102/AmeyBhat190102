from app import orchestrator


def test_is_cold_classification():
    for p in ("opener", "revive", "follow_up_2", "follow_up_3"):
        assert orchestrator._is_cold(p)
    for p in ("reply", "booking_push"):
        assert not orchestrator._is_cold(p)


def test_approval_token_deterministic_and_bound_to_id():
    a = orchestrator.approval_token("msg-1")
    assert a == orchestrator.approval_token("msg-1")
    assert a != orchestrator.approval_token("msg-2")
    assert len(a) == 24
