from app.models import ESCALATE_INTENTS, INTENT_ROUTES, Intent, State, TERMINAL


def test_every_intent_has_a_route():
    assert set(INTENT_ROUTES) == set(Intent)


def test_escalate_intents_freeze_the_lead():
    for intent in ESCALATE_INTENTS:
        state, action = INTENT_ROUTES[intent]
        assert action == "escalate"
        assert state == State.ESCALATED


def test_opt_out_suppresses():
    state, action = INTENT_ROUTES[Intent.OPT_OUT]
    assert (state, action) == (State.OPTED_OUT, "suppress")
    assert State.OPTED_OUT in TERMINAL


def test_booking_accept_hands_off():
    state, action = INTENT_ROUTES[Intent.BOOKING_ACCEPT]
    assert (state, action) == (State.CALL_BOOKED, "handoff")


def test_autoreply_ignored():
    assert INTENT_ROUTES[Intent.AUTOREPLY] == (None, "ignore")
