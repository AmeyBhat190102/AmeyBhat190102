"""State machine definition and shared types. Transitions are explicit; the LLM
never picks a state directly. It emits an intent; the orchestrator maps intent
to a transition through this table."""
from enum import Enum


class State(str, Enum):
    SOURCED = "SOURCED"            # imported, not yet approved for outreach
    QUEUED = "QUEUED"              # cleared by policy for outreach
    CONTACTED = "CONTACTED"        # opener/follow-up sent, awaiting reply
    ENGAGED = "ENGAGED"            # they replied; conversation live
    BOOKING = "BOOKING"            # call link sent / times being agreed
    CALL_BOOKED = "CALL_BOOKED"    # terminal success -> handoff packet
    HANDED_OFF = "HANDED_OFF"      # SK owns the relationship now
    ESCALATED = "ESCALATED"        # frozen, waiting on SK instruction
    NOT_NOW = "NOT_NOW"            # snoozed; one revival later
    LOST = "LOST"
    OPTED_OUT = "OPTED_OUT"        # never contact again


class Intent(str, Enum):
    INTERESTED = "INTERESTED"
    QUESTION = "QUESTION"
    PRICING = "PRICING"
    OBJECTION = "OBJECTION"
    BOOKING_ACCEPT = "BOOKING_ACCEPT"        # said yes to a call / used the link
    TIMES_PROPOSED = "TIMES_PROPOSED"        # gave their own slots
    NOT_NOW = "NOT_NOW"
    NOT_INTERESTED = "NOT_INTERESTED"
    OPT_OUT = "OPT_OUT"
    WRONG_PERSON = "WRONG_PERSON"
    REFERRAL = "REFERRAL"                    # pointed us to someone else
    HUMAN_REQUEST = "HUMAN_REQUEST"
    ANGRY = "ANGRY"
    AUTOREPLY = "AUTOREPLY"                  # OOO etc.
    UNCLEAR = "UNCLEAR"


# Intents that always freeze the lead and page SK, regardless of autonomy level.
ESCALATE_INTENTS = {Intent.PRICING, Intent.HUMAN_REQUEST, Intent.ANGRY, Intent.TIMES_PROPOSED}

# Intent -> (new state, action) for a lead that is currently live
# action: reply | escalate | book | handoff | suppress | snooze | close | requeue | ignore
INTENT_ROUTES = {
    Intent.INTERESTED:     (State.ENGAGED,   "reply"),
    Intent.QUESTION:       (State.ENGAGED,   "reply"),
    Intent.OBJECTION:      (State.ENGAGED,   "reply"),
    Intent.PRICING:        (State.ESCALATED, "escalate"),
    Intent.HUMAN_REQUEST:  (State.ESCALATED, "escalate"),
    Intent.ANGRY:          (State.ESCALATED, "escalate"),
    Intent.TIMES_PROPOSED: (State.ESCALATED, "escalate"),
    Intent.BOOKING_ACCEPT: (State.CALL_BOOKED, "handoff"),
    Intent.NOT_NOW:        (State.NOT_NOW,   "snooze"),
    Intent.NOT_INTERESTED: (State.LOST,      "close"),
    Intent.OPT_OUT:        (State.OPTED_OUT, "suppress"),
    Intent.WRONG_PERSON:   (State.LOST,      "close"),
    Intent.REFERRAL:       (State.LOST,      "escalate"),   # SK decides whether to source the referral
    Intent.AUTOREPLY:      (None,            "ignore"),
    Intent.UNCLEAR:        (State.ENGAGED,   "reply"),
}

TERMINAL = {State.HANDED_OFF, State.LOST, State.OPTED_OUT}
