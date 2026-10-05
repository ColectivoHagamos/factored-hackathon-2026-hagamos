"""Conversation flow of a dispute: a state machine over the event log.

The interpreter only reads the message. This code decides the next step with the policy engine, acts only through the
tools port and its action gate, dates deadlines only with the legal clock, and sends no reply that fails the validator.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from pydantic import JsonValue

from vera.contracts.cases import Case, DisputeReason
from vera.contracts.charges import Candidate, ChargeDetail, ChargeKind, ChargeStatus, FraudScoreBand
from vera.contracts.common import Country, Language, Money
from vera.contracts.conversation import (
    ChargeSummary,
    GlassBoxEntry,
    MessageRequest,
    MessageResponse,
    Option,
    PendingConfirmation,
    Stage,
)
from vera.contracts.events import Event, EventType
from vera.contracts.handoff import (
    Action,
    DeclaredFacts,
    GoodwillCandidate,
    GoodwillCriterion,
    LanguageVariant,
    Queue,
    Sweep,
    Transfer,
    TransferReason,
)
from vera.contracts.interpretation import Answer, ClaimType, DeclaredChannel, Interpretation
from vera.contracts.tools import (
    BlockCardInput,
    CreateHandoffInput,
    CreateTransferInput,
    ReadCaseInput,
    RegisterDisputeInput,
    RegisterDisputeOutput,
    SearchChargesInput,
    SendFraudAlertInput,
    SweepChargesInput,
    ToolError,
    ToolErrorCode,
    ViewChargeInput,
)
from vera.core.events import new_event
from vera.core.legal_route import LegalAssessment, assess
from vera.core.state import FlowState, Step
from vera.output.handoff import CARD_LAST_SEEN, build_handoff, build_transfer
from vera.output.render import Renderer, day, language_of, money, status_word
from vera.output.validator import UnsafeReplyError, check
from vera.policy.engine import Evaluation, Facts, Outcome, PolicyEngine, Signal, exposure_usd
from vera.policy.legal_clock import LegalClock
from vera.ports.event_log import EventLog
from vera.ports.interpreter import InterpreterPort
from vera.ports.tools import Offers, Session, ToolsPort

PENDING_TOKEN = "tok_pending_confirmation"
INVALID_NOTE = ToolError(code=ToolErrorCode.INVALID_SCHEMA)
MAX_TURNS = 40
SEARCH_DAYS = {ChargeKind.PURCHASE: 30, ChargeKind.BANK_ADJUSTMENT: 90}
# With a merchant, a place or an amount to match, older charges are searched too, up to the longest legal window
# (180 days for a charge abroad in Mexico); the legal clock then says whether a route is still open.
NAMED_SEARCH_DAYS = 180
VARIANTS = {Country.MX: LanguageVariant.ES_MX, Country.CO: LanguageVariant.ES_CO, Country.AR: LanguageVariant.ES_AR}
YES_NO = {Language.ES: ("Sí", "No"), Language.PT: ("Sim", "Não")}
# POL-17: "the customer is told nothing"; the decision stays in the log and the handoff, not in the glass box.
INTERNAL_RULES = frozenset({"POL-17"})
POLICY_SOURCE = {
    Language.ES: "Política de disputas de LATAM Bank v{version}",
    Language.PT: "Política de disputas do LATAM Bank v{version}",
}
# The opening menu: each reason VERA covers as a button, in the order a customer looks for it.
MENU = (
    ("unrecognized_charge", "menu_unrecognized"),
    ("improper_charge", "menu_improper"),
    ("lost_card", "menu_lost_card"),
    ("scam_transfer", "menu_scam"),
    ("human_request", "menu_person"),
)
INTENT_CLAIMS = {
    "unrecognized_charge": ClaimType.UNRECOGNIZED_CHARGE,
    "improper_charge": ClaimType.IMPROPER_CHARGE,
    "lost_card": ClaimType.UNRECOGNIZED_CHARGE,
    "scam_transfer": ClaimType.SCAM_TRANSFER,
    "human_request": ClaimType.HUMAN_REQUEST,
}
# A lost or stolen card: the most recent movements shown once the card is protected.
REVIEW_LIMIT = 8
# The five states of the brand for the panel beside the conversation; a step not listed is a verification.
STAGES: dict[Step, Stage] = {
    Step.CHOOSE_CHARGE: "analysis",
    Step.CLARIFY: "analysis",
    Step.CHOOSE_CARD: "analysis",
    Step.HANDED_OFF: "result",
    Step.DONE: "resolved",
}


@dataclass
class Turn:
    """What one turn produces: lines of the reply, options, rule citations and the amounts the tools returned."""

    session: Session
    state: FlowState
    last_event: Event | None
    lines: list[str] = field(default_factory=list)
    options: list[Option] = field(default_factory=list)
    glass_box: list[GlassBoxEntry] = field(default_factory=list)
    amounts: set[str] = field(default_factory=set)
    pending: PendingConfirmation | None = None
    multiple_choice: bool = False
    # The previous reply: what the customer was asked and with which options.
    asked: Event | None = None
    # Rule decisions already recorded in the conversation, as (rule, outcome): each one is recorded once.
    decided: set[tuple[str, str | None]] = field(default_factory=set)
    # The customer wrote this turn, instead of pressing a button.
    typed: bool = False


class Conversation:
    def __init__(
        self,
        *,
        interpreter: InterpreterPort,
        tools: ToolsPort,
        log: EventLog,
        engine: PolicyEngine,
        legal: LegalClock,
        renderer: Renderer,
        now: Callable[[], datetime],
        new_id: Callable[[], str],
    ) -> None:
        self._interpreter = interpreter
        self._tools = tools
        self._log = log
        self._engine = engine
        self._legal = legal
        self._renderer = renderer
        self._now = now
        self._new_id = new_id

    # Public API

    def start(
        self, session: Session, preferred_language: Language | None = None, first_name: str | None = None
    ) -> MessageResponse:
        """The greeting, by name when the customer has one, and the opening menu."""
        customer = self._tools.customer(session)
        if customer is None:
            raise LookupError("unknown customer")
        variant = LanguageVariant.PT if preferred_language is Language.PT else VARIANTS[customer.country]
        state = FlowState(variant=variant)
        turn = Turn(session, state, None)
        turn.lines.append(self._text(turn, "greeting", who=f", {first_name}" if first_name else ""))
        self._menu(turn)
        return self._finish(turn)

    def reply(
        self, session: Session, message: MessageRequest, security_signals: tuple[str, ...] = ()
    ) -> MessageResponse:
        """One customer turn; security_signals come from the gateway, read on the original text."""
        events = self._log.read(session.conversation_id)
        if not events:
            raise LookupError("unknown conversation")
        asked = next(e for e in reversed(events) if e.type is EventType.REPLY)
        turn = Turn(session, FlowState.model_validate(asked.data["state"]), events[-1], asked=asked)
        turn.decided = {(e.data["rule"], e.data.get("outcome")) for e in events if e.type is EventType.RULE_DECISION}
        turns = 1 + sum(1 for event in events if event.type is EventType.CUSTOMER_MESSAGE)
        self._record(turn, EventType.CUSTOMER_MESSAGE, {"text": message.text, "option": message.selected_option})
        if turns > MAX_TURNS:
            self._turn_limit(turn)
        else:
            self._take_turn(turn, message, security_signals)
        self._alert_fraud_if_due(turn)
        return self._finish(turn)

    def history(self, conversation_id: str) -> tuple[Event, ...]:
        """Events of a conversation, for audit and replay."""
        return self._log.read(conversation_id)

    def _take_turn(self, turn: Turn, message: MessageRequest, security_signals: tuple[str, ...]) -> None:
        turn.typed = message.text is not None
        reading = self._interpret(turn, message, flagged=bool(security_signals))
        if security_signals:
            self._security_event(turn, security_signals)
        if reading.asks_if_human and reading.claim_type is not ClaimType.HUMAN_REQUEST:
            # VERA never passes for a person: it says what it is, offers one, and keeps the open question.
            turn.lines.append(self._text(turn, "not_a_person"))
            self._repeat_question(turn)
            return
        if self._safety_first(turn, reading):
            return
        self._validate_emotion(turn, reading, flagged=bool(security_signals))
        if security_signals:
            # POL-03: the message is data; nothing is searched or changed.
            turn.lines.append(self._text(turn, "not_found"))
            self._repeat_question(turn)
        else:
            self._advance(turn, reading)

    # Interpretation and safety

    def _interpret(self, turn: Turn, message: MessageRequest, flagged: bool = False) -> Interpretation:
        language = language_of(turn.state.variant)
        if turn.state.step is Step.ASK_CLAIM and turn.state.claim_type is None:
            expecting = "claim"
        elif turn.state.step in (Step.CHOOSE_CHARGE, Step.SWEEP, Step.CHOOSE_CARD, Step.REVIEW):
            expecting = "choice"
        elif turn.state.step is Step.SCAM_DETAILS:
            expecting = "details"
        else:
            expecting = "yes_no"
        if message.text:
            context = {"language": language.value, "expecting": expecting, "question": turn.state.step.value}
            if flagged:
                # The gateway flagged the text: only deterministic rules read it, never a model it could steer.
                context["flagged"] = "yes"
            reading = self._interpreter.interpret(message.text, context)
            provider = self._interpreter.name
            if message.intent and expecting == "claim" and not _overrides_the_button(reading):
                # The button the customer pressed is the claim; the text still gives the charge and the safety words.
                reading = reading.model_copy(
                    update={
                        "claim_type": INTENT_CLAIMS[message.intent],
                        "has_card": Answer.NO if message.intent == "lost_card" else reading.has_card,
                        "confidence": 1.0,
                    }
                )
        else:
            option = message.selected_option
            # A reason of the opening menu reads as the claim the customer would have written.
            intent = option if isinstance(option, str) and option in INTENT_CLAIMS else None
            reading = Interpretation(
                claim_type=INTENT_CLAIMS[intent] if intent else turn.state.claim_type or ClaimType.UNRECOGNIZED_CHARGE,
                has_card=Answer.NO if intent == "lost_card" else Answer.NOT_SAID,
                answer=Answer(option) if option in ("yes", "no") else Answer.NOT_SAID,
                selected_numbers=(option,) if isinstance(option, int) else (),
                language=language,
                confidence=1.0,
            )
            provider = "option"
        self._record(turn, EventType.INTERPRETATION, reading.model_dump(mode="json"), provider)
        if reading.language is Language.PT and turn.state.variant is not LanguageVariant.PT:
            turn.state = turn.state.advance(variant=LanguageVariant.PT)
        return reading

    def _safety_first(self, turn: Turn, reading: Interpretation) -> bool:
        """POL-01, POL-02 and POL-09 win over every other step."""
        customer = self._tools.customer(turn.session)
        # During the key questions of a scam a person is already on the way (POL-10): the request needs no offer.
        person = reading.claim_type is ClaimType.HUMAN_REQUEST and turn.state.step is not Step.SCAM_DETAILS
        sure = reading.confidence >= self._engine.parameters.interpreter_min_confidence
        if person and not sure and turn.state.step not in (Step.HANDED_OFF, Step.PERSON_OFFERED):
            # POL-14 before POL-01: when the reading is unsure, VERA asks before treating it as a request.
            turn.lines.append(self._text(turn, "offer_person"))
            self._yes_no(turn)
            turn.state = turn.state.advance(step=Step.CONFIRM_PERSON, resume_step=self._open_question(turn))
            return True
        facts = Facts(
            account_country=customer.country,
            human_requested=person,
            person_offers_made=turn.state.person_offers,
            coercion=reading.coercion,
            regulator_mentioned=reading.regulator_mentioned,
            already_escalated=turn.state.escalated,
        )
        evaluation = self._evaluate(turn, facts)
        if turn.state.step is Step.HANDED_OFF:
            return False
        if not ({Outcome.HANDOFF, Outcome.INFORM_VENUE} & evaluation.outcomes):
            # POL-01 alone: one offer to go on first. Coercion and the regulator never wait for an offer.
            if Outcome.OFFER_BEFORE_TRANSFER in evaluation.outcomes:
                self._offer_before_transfer(turn)
                return True
            return False
        if reading.coercion:
            turn.lines.append(self._text(turn, "safety"))
            reason = TransferReason.COERCION
        elif Outcome.INFORM_VENUE in evaluation.outcomes:
            turn.lines.append(self._text(turn, "regulator", venue=_venue(customer.country)))
            reason = TransferReason.REGULATOR
        else:
            turn.lines.append(self._text(turn, "handoff_now"))
            reason = TransferReason.PERSON_REQUESTED
        self._hand_off(turn, evaluation.queue or Queue.COMPLAINTS, reason)
        return True

    def _validate_emotion(self, turn: Turn, reading: Interpretation, flagged: bool) -> None:
        """Worry, fear or anger is acknowledged before the next step, in words that change each time.

        A clear claim in the first message is answered by its own empathy, so it is not acknowledged twice."""
        sure = reading.confidence >= self._engine.parameters.interpreter_min_confidence
        opening_claim = (
            turn.state.step is Step.ASK_CLAIM
            and turn.state.claim_type is None
            and sure
            and not reading.greeting
            and reading.claim_type is not ClaimType.OUT_OF_SCOPE
        )
        if not reading.distress or flagged or opening_claim:
            return
        turn.lines.append(self._text(turn, "calm", pick=turn.state.calmed))
        turn.state = turn.state.advance(calmed=turn.state.calmed + 1)

    def _security_event(self, turn: Turn, signals: tuple[str, ...]) -> None:
        """POL-03: every attempt is recorded with its signals, also when a person takes over."""
        facts = Facts(
            account_country=self._country(turn),
            instruction_in_message=any(s != "other_customer" for s in signals),
            foreign_charge_requested="other_customer" in signals,
            already_escalated=turn.state.escalated,
        )
        self._evaluate(turn, facts)
        self._record(turn, EventType.SECURITY_EVENT, {"rule": "POL-03", "signals": [*signals]})

    def _turn_limit(self, turn: Turn) -> None:
        """LLM10: past the limit nothing more is interpreted and the conversation goes to a person once."""
        if turn.state.step is not Step.HANDED_OFF:
            self._record(turn, EventType.RULE_DECISION, {"rule": "turn_limit", "turns": MAX_TURNS})
            self._hand_off(turn, turn.state.queue or Queue.COMPLAINTS, TransferReason.TURN_LIMIT)
        turn.lines.append(self._text(turn, "turn_limit"))

    # State machine

    def _advance(self, turn: Turn, reading: Interpretation) -> None:
        # At the POL-01 offer or the key questions of a scam, a message on the side still leads to the person.
        if turn.state.step not in (Step.ASK_CLAIM, Step.PERSON_OFFERED, Step.SCAM_DETAILS) and _aside(reading):
            self._answer_aside(turn, reading)
            return
        handlers = {
            Step.ASK_CLAIM: self._on_claim,
            Step.CHOOSE_CHARGE: self._on_choice,
            Step.CLARIFY: self._on_clarify,
            Step.ASK_CHANNEL: self._on_channel,
            Step.ASK_CARD: self._on_card,
            Step.SWEEP: self._on_sweep,
            Step.CONFIRM_BLOCK: self._on_block,
            Step.CONFIRM_REGISTER: self._on_register,
            Step.CONFIRM_PERSON: self._on_person,
            Step.PERSON_OFFERED: self._on_person_offer,
            Step.SCAM_DETAILS: self._on_scam_details,
            Step.CHOOSE_CARD: self._on_choose_card,
            Step.REVIEW: self._on_review,
        }
        handler = handlers.get(turn.state.step)
        if handler is None:
            self._after_the_end(turn, reading)
            return
        handler(turn, reading)

    def _after_the_end(self, turn: Turn, reading: Interpretation) -> None:
        """A message after the end: with a person on the way VERA says so; after a closing, a new reason starts over."""
        sure = reading.confidence >= self._engine.parameters.interpreter_min_confidence
        new_claim = sure and not reading.greeting and reading.claim_type is not ClaimType.OUT_OF_SCOPE
        if turn.state.step is Step.DONE and new_claim:
            turn.state = FlowState(variant=turn.state.variant)
            self._on_claim(turn, reading)
            return
        template = "after_handoff" if turn.state.step is Step.HANDED_OFF else "after_done"
        turn.lines.append(self._text(turn, template, pick=turn.state.nudges))
        if template == "after_done":
            self._menu(turn)
        turn.state = turn.state.advance(nudges=turn.state.nudges + 1)

    def _answer_aside(self, turn: Turn, reading: Interpretation) -> None:
        """What VERA does not cover is said and oriented (POL-15 for Pix); the open question stays open."""
        evaluation = self._evaluate(
            turn, Facts(account_country=self._country(turn), pix_mentioned=reading.pix_mentioned)
        )
        turn.lines.append(self._text(turn, "pix" if Outcome.OUT_OF_SCOPE in evaluation.outcomes else "out_of_scope"))
        self._repeat_question(turn)

    def _person_requested(self, turn: Turn) -> None:
        """POL-01 once the request is clear: an offer while one is due, then a person with what is already known."""
        facts = Facts(
            account_country=self._country(turn),
            human_requested=True,
            person_offers_made=turn.state.person_offers,
            already_escalated=turn.state.escalated,
        )
        evaluation = self._evaluate(turn, facts)
        if Outcome.OFFER_BEFORE_TRANSFER in evaluation.outcomes:
            self._offer_before_transfer(turn)
            return
        turn.lines.append(self._text(turn, "handoff_now"))
        self._hand_off(turn, evaluation.queue or Queue.COMPLAINTS, TransferReason.PERSON_REQUESTED)

    def _offer_before_transfer(self, turn: Turn) -> None:
        """POL-01 (v1.5): VERA offers to review the case first; nothing runs while the offer is open."""
        turn.lines.append(self._text(turn, "offer_before_transfer"))
        self._yes_no(turn)
        turn.state = turn.state.advance(
            step=Step.PERSON_OFFERED,
            resume_step=self._open_question(turn),
            person_offers=turn.state.person_offers + 1,
        )

    def _on_person_offer(self, turn: Turn, reading: Interpretation) -> None:
        sure = reading.confidence >= self._engine.parameters.interpreter_min_confidence
        # A claim written in so many words takes the offer, even when it starts with "no": VERA goes on with it.
        tells_what_happened = (
            turn.typed
            and sure
            and not reading.greeting
            and reading.claim_type not in (ClaimType.HUMAN_REQUEST, ClaimType.OUT_OF_SCOPE)
            and self._open_question(turn) is Step.ASK_CLAIM
        )
        if tells_what_happened:
            turn.state = turn.state.advance(step=Step.ASK_CLAIM, resume_step=None)
            self._on_claim(turn, reading)
        elif reading.answer is Answer.YES:
            self._resume(turn)
        else:
            # The customer insists, or does not take the offer.
            self._person_requested(turn)

    def _on_scam_details(self, turn: Turn, reading: Interpretation) -> None:
        """POL-10: whatever the answer, Fraud gets it with the case, and a transfer has no chargeback to promise."""
        turn.state = turn.state.advance(
            date_text=reading.date_text or turn.state.date_text,
            contacted_by=reading.contact_channel or turn.state.contacted_by,
        )
        turn.lines.append(self._text(turn, "scam_handoff"))
        self._hand_off(turn, Queue.FRAUD, TransferReason.SCAM_TRANSFER)

    def _on_person(self, turn: Turn, reading: Interpretation) -> None:
        """POL-14: the customer says whether the unsure reading was a request for a person."""
        if reading.answer is Answer.YES:
            self._person_requested(turn)
        elif reading.answer is Answer.NO:
            self._resume(turn)
        else:
            # Neither yes nor no: the message answers the question that was open before.
            turn.state = turn.state.advance(step=self._open_question(turn), resume_step=None)
            self._advance(turn, reading)

    def _open_question(self, turn: Turn) -> Step:
        """The step of the question the customer was answering before a detour about a person."""
        return turn.state.resume_step or turn.state.step

    def _resume(self, turn: Turn) -> None:
        """Back to the open question with its options and attempts; a pending action needs a new yes."""
        step = self._open_question(turn)
        replies = [e for e in self._log.read(turn.session.conversation_id) if e.type is EventType.REPLY]
        turn.asked = next((e for e in reversed(replies) if e.data["state"]["step"] == step.value), None)
        attempts = turn.asked.data["state"]["attempts"] if turn.asked else 0
        turn.state = turn.state.advance(step=step, resume_step=None, attempts=attempts)
        self._repeat_question(turn)

    def _on_claim(self, turn: Turn, reading: Interpretation) -> None:
        if turn.state.claim_type is not None:
            # The claim is known and VERA asked for a detail: this message only narrows the search.
            known = turn.state.claim_type is ClaimType.IMPROPER_CHARGE and not turn.state.duplicate
            self._search(turn, reading, ChargeKind.BANK_ADJUSTMENT if known else ChargeKind.PURCHASE)
            return
        if reading.duplicate and reading.claim_type in (ClaimType.IMPROPER_CHARGE, ClaimType.UNRECOGNIZED_CHARGE):
            # A purchase charged twice is an improper charge whatever the reader called it; the purchase is known.
            reading = reading.model_copy(update={"claim_type": ClaimType.IMPROPER_CHARGE})
        sure = reading.confidence >= self._engine.parameters.interpreter_min_confidence
        if reading.greeting and (reading.claim_type is ClaimType.OUT_OF_SCOPE or not sure):
            # A greeting, small talk or a plea for help: warm words and the menu, never a question about a charge.
            self._welcome(turn, "welcome")
            return
        customer = self._tools.customer(turn.session)
        evaluation = self._evaluate(
            turn,
            Facts(
                account_country=customer.country,
                claim_type=reading.claim_type,
                interpreter_confidence=reading.confidence,
                pix_mentioned=reading.pix_mentioned,
                already_escalated=turn.state.escalated,
            ),
        )
        if Outcome.OUT_OF_SCOPE in evaluation.outcomes:
            turn.lines.append(self._text(turn, "pix"))
            self._menu(turn)
            return
        if reading.claim_type is ClaimType.OUT_OF_SCOPE:
            self._welcome(turn, "out_of_scope_opening")
            return
        if Outcome.ASK_INSTEAD_OF_ACT in evaluation.outcomes:
            self._ask_again(turn, "low_confidence")
            return
        if reading.claim_type is ClaimType.SCAM_TRANSFER:
            turn.state = turn.state.advance(
                claim_type=reading.claim_type, authorized_payment=reading.authorized_payment
            )
            if reading.date_text and reading.contact_channel:
                # The customer already said when and how: nothing to ask again.
                self._on_scam_details(turn, reading)
                return
            turn.lines.append(self._text(turn, "scam"))
            turn.state = turn.state.advance(
                step=Step.SCAM_DETAILS, date_text=reading.date_text, contacted_by=reading.contact_channel
            )
            return
        duplicate = reading.duplicate and reading.claim_type is ClaimType.IMPROPER_CHARGE
        improper = reading.claim_type is ClaimType.IMPROPER_CHARGE and not duplicate
        kind = ChargeKind.BANK_ADJUSTMENT if improper else ChargeKind.PURCHASE
        turn.state = turn.state.advance(
            claim_type=reading.claim_type, declared_channel=reading.declared_channel, duplicate=duplicate
        )
        if reading.has_card is not Answer.NOT_SAID:
            turn.state = turn.state.advance(has_card=reading.has_card)
        if kind is ChargeKind.PURCHASE and turn.state.has_card is Answer.NO and not duplicate:
            self._protect_first(turn)
            return
        turn.lines.append(self._text(turn, "duplicate" if duplicate else "improper" if improper else "empathy"))
        self._search(turn, reading, kind)

    def _welcome(self, turn: Turn, template: str) -> None:
        """At the opening, warm words that change each time they come back, and the menu of what VERA covers."""
        turn.lines.append(self._text(turn, template, pick=turn.state.nudges))
        self._menu(turn)
        turn.state = turn.state.advance(nudges=turn.state.nudges + 1)

    def _menu(self, turn: Turn) -> None:
        turn.options.extend(
            Option(n=n, label=self._text(turn, label), answer=intent) for n, (intent, label) in enumerate(MENU, 1)
        )

    # A lost or stolen card

    def _protect_first(self, turn: Turn) -> None:
        """POL-06: the card is protected before anything else, and its recent movements are reviewed afterwards."""
        turn.lines.append(self._text(turn, "lost_card_empathy"))
        today = self._now().date()
        args = SearchChargesInput(
            date_from=today - timedelta(days=SEARCH_DAYS[ChargeKind.PURCHASE]), date_to=today, kind=ChargeKind.PURCHASE
        )
        result = self._tools.search_charges(turn.session, self._offers(turn), args)
        self._record_tool(turn, "search_charges", args.model_dump(mode="json"), result)
        if _no_results(result):
            # No recent purchase names the card: a person of the Fraud team protects it.
            turn.lines.append(self._text(turn, "lost_card_no_movements"))
            self._hand_off(turn, Queue.FRAUD, TransferReason.LOST_CARD)
            return
        if isinstance(result, ToolError):
            self._fail(turn)
            return
        output, offers = result
        turn.state = turn.state.advance(
            charges_offered=offers.charges, cards_offered=offers.cards, review_after_block=True, attempts=0
        )
        cards = {c.card_n: c.card or "" for c in output.candidates if c.card_n is not None}
        if len(cards) > 1:
            turn.lines.append(self._text(turn, "choose_card"))
            turn.options.extend(Option(n=n, label=label) for n, label in sorted(cards.items()))
            turn.state = turn.state.advance(step=Step.CHOOSE_CARD)
            return
        if not cards:
            self._review_movements(turn)
            return
        card_n, card = next(iter(cards.items()))
        self._protect_card(turn, card_n, card)

    def _on_choose_card(self, turn: Turn, reading: Interpretation) -> None:
        chosen = [n for n in reading.selected_numbers if n in turn.state.cards_offered]
        if not chosen:
            self._ask_again(turn, "choose_card", step=Step.CHOOSE_CARD)
            return
        shown = {o["n"]: o["label"] for o in (turn.asked.data.get("options", []) if turn.asked else [])}
        self._protect_card(turn, chosen[0], shown.get(chosen[0], ""))

    def _protect_card(self, turn: Turn, card_n: int, card: str) -> None:
        turn.state = turn.state.advance(signals=[Signal.CARD_NOT_IN_POSSESSION])
        evaluation = self._evaluate(turn, self._dispute_facts(turn, []))
        on_request = Outcome.BLOCK_ON_CUSTOMER_REQUEST in evaluation.outcomes
        self._propose_block(turn, card_n, card, "lost_card_block_on_request" if on_request else "lost_card_block")

    def _review_movements(self, turn: Turn) -> None:
        """Once the card is protected, the recent movements: the customer marks the ones they did not make."""
        recent = sorted(turn.state.charges_offered)[:REVIEW_LIMIT]
        details = [d for d in (self._detail(turn, n) for n in recent) if d is not None]
        turn.lines.append(self._text(turn, "review_movements"))
        turn.options.extend(Option(n=d.n, label=self._receipt(turn, d)) for d in details)
        turn.multiple_choice = True
        turn.state = turn.state.advance(
            step=Step.REVIEW, swept=[d.n for d in details], review_after_block=False, chosen=None
        )

    def _on_review(self, turn: Turn, reading: Interpretation) -> None:
        offered = set(turn.state.swept)
        if reading.selected_numbers:
            unrecognized = [n for n in reading.selected_numbers if n in offered]
        elif reading.answer is Answer.NO:
            unrecognized = sorted(offered)
        else:
            unrecognized = []
        if not unrecognized:
            # As in the sweep, «todos» means the customer recognizes every movement shown.
            turn.lines.append(self._text(turn, "recognized_all"))
            turn.lines.append(self._text(turn, "closing"))
            turn.state = turn.state.advance(step=Step.DONE)
            return
        self._assess_signals(turn, unrecognized, offer_block=False)

    def _search(self, turn: Turn, reading: Interpretation, kind: ChargeKind) -> None:
        today = self._now().date()
        named = reading.amount is not None or reading.merchant_text is not None
        args = SearchChargesInput(
            date_from=today - timedelta(days=NAMED_SEARCH_DAYS if named else SEARCH_DAYS[kind]),
            date_to=today,
            amount=reading.amount,
            merchant=reading.merchant_text,
            kind=kind,
        )
        result = self._tools.search_charges(turn.session, self._offers(turn), args)
        self._record_tool(turn, "search_charges", args.model_dump(mode="json"), result)
        missed = _no_results(result) and reading.merchant_text is not None
        if missed:
            # The merchant written by the customer may not match the statement; try the recent window without it.
            args = args.model_copy(update={"merchant": None, "date_from": today - timedelta(days=SEARCH_DAYS[kind])})
            result = self._tools.search_charges(turn.session, self._offers(turn), args)
            self._record_tool(turn, "search_charges", args.model_dump(mode="json"), result)
        if _no_results(result):
            self._ask_again(turn, "ask_detail")
            return
        if isinstance(result, ToolError):
            self._fail(turn)
            return
        output, offers = result
        turn.state = turn.state.advance(charges_offered=offers.charges, cards_offered=offers.cards, attempts=0)
        # AC-2: a charge other than the one named is never presented as the one in question; the customer chooses.
        if len(output.candidates) == 1 and not missed:
            self._clarify(turn, output.candidates[0].n)
            return
        self._evaluate(turn, Facts(account_country=self._country(turn), candidates_found=len(output.candidates)))
        turn.lines.append(self._text(turn, "named_not_found" if missed else "choose_charge"))
        turn.options.extend(Option(n=c.n, label=self._receipt(turn, c)) for c in output.candidates)
        turn.state = turn.state.advance(step=Step.CHOOSE_CHARGE)

    def _on_choice(self, turn: Turn, reading: Interpretation) -> None:
        offered = [n for n in reading.selected_numbers if n in turn.state.charges_offered]
        if not offered:
            self._ask_again(turn, "choose_charge", step=Step.CHOOSE_CHARGE)
            return
        self._clarify(turn, offered[0])

    def _clarify(self, turn: Turn, n: int) -> None:
        detail = self._tools.view_charge(turn.session, self._offers(turn), ViewChargeInput(candidate_n=n))
        self._record_tool(turn, "view_charge", {"candidate_n": n}, detail)
        if isinstance(detail, ToolError):
            self._fail(turn)
            return
        turn.lines.append(self._receipt(turn, detail))
        if detail.status is not ChargeStatus.APPROVED:
            self._evaluate(turn, Facts(account_country=self._country(turn), charge_status=detail.status))
            turn.lines.append(self._text(turn, f"status_{detail.status.value}"))
        if detail.is_known_merchant:
            turn.lines.append(self._text(turn, "known_merchant"))
        improper = turn.state.claim_type is ClaimType.IMPROPER_CHARGE
        turn.lines.append(self._text(turn, "ask_is_this_charge" if improper else "ask_recognize"))
        self._yes_no(turn)
        turn.state = turn.state.advance(step=Step.CLARIFY, chosen=n, disputed=[n])

    def _on_clarify(self, turn: Turn, reading: Interpretation) -> None:
        if turn.state.claim_type is ClaimType.IMPROPER_CHARGE:
            if reading.answer is Answer.YES:
                self._propose_registration(turn)
            else:
                self._ask_again(turn, "ask_detail", step=Step.ASK_CLAIM)
            return
        if reading.answer is Answer.YES:
            turn.lines.append(self._text(turn, "recognized"))
            turn.lines.append(self._text(turn, "closing"))
            turn.state = turn.state.advance(step=Step.DONE)
            return
        if reading.answer is Answer.NOT_SAID:
            self._ask_again(turn, "ask_recognize", step=Step.CLARIFY)
            return
        if turn.state.declared_channel is None:
            turn.lines.append(self._text(turn, "ask_channel"))
            self._yes_no(turn)
            turn.options.append(Option(n=3, label=self._text(turn, "not_sure"), answer="not_sure"))
            turn.state = turn.state.advance(step=Step.ASK_CHANNEL)
            return
        self._ask_card_or_sweep(turn)

    def _on_channel(self, turn: Turn, reading: Interpretation) -> None:
        channel = reading.declared_channel or {
            Answer.YES: DeclaredChannel.ONLINE,
            Answer.NO: DeclaredChannel.IN_PERSON,
        }.get(reading.answer, DeclaredChannel.UNKNOWN)
        turn.state = turn.state.advance(declared_channel=channel)
        self._ask_card_or_sweep(turn)

    def _ask_card_or_sweep(self, turn: Turn) -> None:
        if turn.state.has_card is Answer.NOT_SAID:
            turn.lines.append(self._text(turn, "ask_card"))
            self._yes_no(turn)
            turn.state = turn.state.advance(step=Step.ASK_CARD)
            return
        self._sweep(turn)

    def _on_card(self, turn: Turn, reading: Interpretation) -> None:
        answer = reading.has_card if reading.has_card is not Answer.NOT_SAID else reading.answer
        turn.state = turn.state.advance(has_card=answer)
        self._sweep(turn)

    def _sweep(self, turn: Turn) -> None:
        result = self._tools.sweep_charges(
            turn.session, self._offers(turn), SweepChargesInput(candidate_n=turn.state.chosen)
        )
        self._record_tool(turn, "sweep_charges", {"candidate_n": turn.state.chosen}, result)
        if isinstance(result, ToolError) and result.code is ToolErrorCode.FAILURE:
            self._fail(turn)
            return
        if isinstance(result, ToolError):
            self._assess_signals(turn, unrecognized=[])
            return
        output, offers = result
        turn.state = turn.state.advance(charges_offered=offers.charges, cards_offered=offers.cards)
        others = [c for c in output.charges if c.n != turn.state.chosen]
        if not others:
            self._assess_signals(turn, unrecognized=[])
            return
        turn.lines.append(self._text(turn, "sweep"))
        turn.options.extend(Option(n=c.n, label=self._receipt(turn, c)) for c in others)
        turn.multiple_choice = True
        turn.state = turn.state.advance(step=Step.SWEEP, swept=[c.n for c in others])

    def _on_sweep(self, turn: Turn, reading: Interpretation) -> None:
        # Only the charges shown in the sweep can be disowned here, never others listed earlier (AC-2).
        offered = set(turn.state.swept)
        if reading.selected_numbers:
            unrecognized = [n for n in reading.selected_numbers if n in offered]
        elif reading.answer is Answer.NO:
            unrecognized = sorted(offered)
        else:
            unrecognized = []
        self._assess_signals(turn, unrecognized)

    def _assess_signals(self, turn: Turn, unrecognized: list[int], offer_block: bool = True) -> None:
        details = [self._detail(turn, n) for n in [turn.state.chosen, *unrecognized]]
        details = [d for d in details if d is not None]
        signals: set[Signal] = set()
        if turn.state.has_card is Answer.NO:
            signals.add(Signal.CARD_NOT_IN_POSSESSION)
        if len(details) >= self._engine.parameters.unrecognized_charges_signal:
            signals.add(Signal.MULTIPLE_UNRECOGNIZED)
        if any(d.fraud_score_band is FraudScoreBand.ABOVE_30 for d in details):
            signals.add(Signal.FRAUD_SCORE_ABOVE_THRESHOLD)
        if any(d.status is not ChargeStatus.APPROVED for d in details):
            signals.add(Signal.UNRECOGNIZED_NON_APPROVED)
        if any(not d.is_known_merchant for d in details):
            signals.add(Signal.NEW_MERCHANT)
        disputed = [d.n for d in details if d.status in (ChargeStatus.APPROVED, ChargeStatus.PENDING)]
        turn.state = turn.state.advance(signals=sorted(signals), disputed=disputed)
        evaluation = self._evaluate(turn, self._dispute_facts(turn, details))
        if Outcome.FRAUD_ALERT in evaluation.outcomes:
            turn.state = turn.state.advance(fraud_alert_charges=[d.n for d in details])
        card_n = details[0].card_n if details and offer_block else None
        if Outcome.OFFER_BLOCK in evaluation.outcomes and card_n:
            self._propose_block(turn, card_n, details[0].card, "offer_block")
        elif Outcome.BLOCK_ON_CUSTOMER_REQUEST in evaluation.outcomes and card_n:
            self._propose_block(turn, card_n, details[0].card, "block_on_request")
        else:
            self._propose_registration(turn)

    def _propose_block(self, turn: Turn, card_n: int, card: str | None, template: str) -> None:
        args = BlockCardInput(card_n=card_n, confirmation_token=PENDING_TOKEN)
        confirmation = self._tools.confirm(turn.session, "block_card", args)
        args = args.model_copy(update={"confirmation_token": confirmation.token})
        turn.lines.append(self._text(turn, template, card=card or ""))
        self._yes_no(turn)
        turn.pending = PendingConfirmation(
            action="block_card", summary=card or "card", expires_at=_aware(confirmation.expires_at)
        )
        turn.state = turn.state.advance(
            step=Step.CONFIRM_BLOCK, pending_tool="block_card", pending_arguments=args.model_dump(mode="json")
        )

    def _on_block(self, turn: Turn, reading: Interpretation) -> None:
        if reading.answer is Answer.YES:
            args = BlockCardInput.model_validate(turn.state.pending_arguments)
            result = self._tools.block_card(turn.session, self._offers(turn), args)
            self._record_write(turn, "block_card", args, result.output, result.read_back_matches)
            if not result.read_back_matches:
                self._fail(turn)
                return
            pending = (turn.asked.data.get("pending") or {}) if turn.asked else {}
            card = next((c for c in self._case_cards(turn)), pending.get("summary", ""))
            turn.lines.append(self._text(turn, "block_done", card=card))
        elif reading.answer is Answer.NO:
            turn.lines.append(self._text(turn, "block_skipped"))
        else:
            self._ask_again(turn, "confirm_options", step=Step.CONFIRM_BLOCK)
            return
        if turn.state.review_after_block:
            self._review_movements(turn)
            return
        self._propose_registration(turn)

    def _propose_registration(self, turn: Turn) -> None:
        details = [d for d in (self._detail(turn, n) for n in turn.state.disputed) if d is not None]
        approved = [d for d in details if d.status is ChargeStatus.APPROVED]
        if not approved:
            turn.lines.append(self._text(turn, "closing"))
            turn.state = turn.state.advance(step=Step.DONE, pending_tool=None, pending_arguments=None)
            return
        exposure = _exposure(approved)
        if turn.state.duplicate:
            reason = DisputeReason.DUPLICATE
        elif turn.state.claim_type is ClaimType.IMPROPER_CHARGE:
            reason = DisputeReason.BANK_CHARGE
        else:
            reason = DisputeReason.FRAUD
        args = RegisterDisputeInput(
            charges_n=[d.n for d in details],
            reason=reason,
            declared_channel=turn.state.declared_channel or DeclaredChannel.UNKNOWN,
            confirmation_token=PENDING_TOKEN,
        )
        confirmation = self._tools.confirm(turn.session, "register_dispute", args)
        args = args.model_copy(update={"confirmation_token": confirmation.token})
        shown = " + ".join(self._money(turn, m) for m in exposure)
        turn.lines.append(self._text(turn, "confirm_register", charges=_charges(turn, len(details)), exposure=shown))
        self._yes_no(turn)
        turn.pending = PendingConfirmation(
            action="register_dispute", summary=shown, expires_at=_aware(confirmation.expires_at)
        )
        turn.state = turn.state.advance(
            step=Step.CONFIRM_REGISTER, pending_tool="register_dispute", pending_arguments=args.model_dump(mode="json")
        )

    def _on_register(self, turn: Turn, reading: Interpretation) -> None:
        if reading.answer is Answer.NO:
            turn.lines.append(self._text(turn, "closing"))
            turn.state = turn.state.advance(step=Step.DONE, pending_tool=None, pending_arguments=None)
            return
        if reading.answer is not Answer.YES:
            self._ask_again(turn, "confirm_options", step=Step.CONFIRM_REGISTER)
            return
        args = RegisterDisputeInput.model_validate(turn.state.pending_arguments)
        claim = turn.state.claim_type or ClaimType.UNRECOGNIZED_CHARGE
        result = self._tools.register_dispute(turn.session, self._offers(turn), args, claim)
        self._record_write(turn, "register_dispute", args, result.output, result.read_back_matches)
        if isinstance(result.output, ToolError) and result.output.case_id:
            self._repeat_case(turn, result.output.case_id)
            return
        if not (result.read_back_matches and isinstance(result.output, RegisterDisputeOutput)):
            self._fail(turn)
            return
        case = self._tools.read_case(turn.session, ReadCaseInput(case_id=result.output.case_id))
        if isinstance(case, ToolError):
            self._fail(turn)
            return
        turn.lines.append(self._text(turn, "case_registered", case_id=result.output.case_id))
        turn.state = turn.state.advance(case_id=result.output.case_id, pending_tool=None, pending_arguments=None)
        legal = self._legal_lines(turn, case)
        self._close_case(turn, case, legal)

    def _repeat_case(self, turn: Turn, case_id: str) -> None:
        """A charge already in a case gets that case and its deadlines, never a second case."""
        turn.lines.append(self._text(turn, "repeat_case", case_id=case_id))
        case = self._tools.read_case(turn.session, ReadCaseInput(case_id=case_id))
        if isinstance(case, Case):
            self._legal_lines(turn, case)
        turn.lines.append(self._text(turn, "closing"))
        turn.state = turn.state.advance(step=Step.DONE, case_id=case_id, pending_tool=None, pending_arguments=None)

    # Closing a registered case

    def _legal_lines(self, turn: Turn, case: Case) -> LegalAssessment:
        """Deadlines of the case, counted from the day it was filed and with the channel it was filed with."""
        first = min(case.charges, key=lambda charge: charge.occurred_at)
        legal = assess(
            self._legal,
            self._country(turn),
            case.declared_channel,
            first.country,
            first.card_type,
            event_day=first.occurred_at.date(),
            filing_day=case.created_at.date(),
        )
        language = language_of(turn.state.variant)
        for due in legal.dues:
            if due.due is None or due.party.value != "bank":
                continue
            name = f"deadline_{due.rule_id}"
            if due.rule_id == "AR-R05":
                name = "deadline_AR-R05_ack" if "acknowledge" in due.what else "deadline_AR-R05_answer"
            turn.lines.append(self._text(turn, name, date=day(due.due, language)))
            rule = self._legal.rule(due.rule_id)
            turn.glass_box.append(
                GlassBoxEntry(
                    rule_id=due.rule_id, source=f"{rule.source.title}, {rule.source.provision}", deadline=due.due
                )
            )
        for step in legal.without_date:
            turn.lines.append(self._text(turn, "route_without_date", route=step.name[language.value]))
        return legal

    def _close_case(self, turn: Turn, case: Case, legal: LegalAssessment) -> None:
        customer = self._tools.customer(turn.session)
        signals = set(turn.state.signals)
        evaluation = self._evaluate(turn, self._dispute_facts(turn, [], case=case))
        escalate = evaluation.escalate or turn.state.escalated
        if escalate:
            queue = evaluation.queue or turn.state.queue or Queue.COMPLAINTS
            goodwill = Outcome.GOODWILL_CANDIDATE in evaluation.outcomes
            details = [d for d in (self._detail(turn, n) for n in turn.state.disputed) if d is not None]
            band = (
                FraudScoreBand.ABOVE_30
                if any(d.fraud_score_band is FraudScoreBand.ABOVE_30 for d in details)
                else (FraudScoreBand.AT_MOST_30)
            )
            handoff = build_handoff(
                case=case,
                customer=customer,
                variant=turn.state.variant,
                response_level=3 if "POL-06" in turn.state.rules_applied else 2,
                fraud_score_band=band,
                declared=DeclaredFacts(channel=turn.state.declared_channel, has_card=turn.state.has_card),
                sweep=Sweep(charges_reviewed=len(turn.state.charges_offered), not_recognized=len(turn.state.disputed)),
                actions=self._actions(turn),
                legal=legal,
                risk_signals=tuple(sorted(s.value for s in signals if s is not Signal.NEW_MERCHANT)),
                fraud_alert=Outcome.FRAUD_ALERT in evaluation.outcomes,
                goodwill=GoodwillCandidate(
                    flagged=goodwill,
                    criteria=tuple(GoodwillCriterion) if goodwill else (),
                    reason="policy section 11.1 criteria met" if goodwill else None,
                ),
                queue=queue,
                rules_applied=tuple(dict.fromkeys(turn.state.rules_applied)),
                open_questions=(CARD_LAST_SEEN,) if Signal.CARD_NOT_IN_POSSESSION in signals else (),
                policy_version=self._engine.version,
                created_at=_aware(self._now()),
            )
            result = self._tools.create_handoff(
                turn.session, CreateHandoffInput(case_id=case.case_id, queue=queue), handoff
            )
            self._record(
                turn, EventType.HANDOFF, {"case_id": case.case_id, "queue": queue.value, "ok": result.read_back_matches}
            )
            turn.lines.append(self._text(turn, "handoff_pt" if turn.state.variant is LanguageVariant.PT else "handoff"))
            turn.state = turn.state.advance(escalated=True, queue=queue)
        if Outcome.FRAUD_ALERT in evaluation.outcomes and not turn.state.fraud_alert_charges:
            turn.state = turn.state.advance(fraud_alert_charges=[charge.n for charge in case.charges])
        turn.lines.append(self._text(turn, "closing"))
        turn.state = turn.state.advance(step=Step.HANDED_OFF if escalate else Step.DONE)

    # Helpers

    def _dispute_facts(self, turn: Turn, details: list[ChargeDetail], case: Case | None = None) -> Facts:
        exposure = case.total_exposure if case else _exposure([d for d in details if d.status is ChargeStatus.APPROVED])
        usd = exposure_usd(exposure, self._engine.parameters.usd_rates)
        return Facts(
            account_country=self._country(turn),
            claim_type=turn.state.claim_type,
            signals=frozenset(turn.state.signals),
            total_exposure_usd=usd,
            disputes_in_window=self._tools.disputes_in_last_days(
                turn.session, self._engine.parameters.repeat_window_days
            ),
            first_dispute_in_goodwill_window=self._tools.disputes_in_last_days(
                turn.session, self._engine.parameters.goodwill_window_days
            )
            == 0,
            bank_charge=turn.state.claim_type is ClaimType.IMPROPER_CHARGE,
            already_escalated=turn.state.escalated,
        )

    def _evaluate(self, turn: Turn, facts: Facts) -> Evaluation:
        evaluation = self._engine.evaluate(facts)
        for decision in evaluation.decisions:
            key = (decision.rule, decision.outcome.value)
            if key in turn.decided and decision.outcome is not Outcome.FRAUD_ALERT:
                continue
            turn.decided.add(key)
            self._record(turn, EventType.RULE_DECISION, decision.as_event_data())
            source = POLICY_SOURCE[language_of(turn.state.variant)].format(version=decision.version)
            entry = GlassBoxEntry(rule_id=decision.rule, source=source)
            if decision.rule not in INTERNAL_RULES and entry not in turn.glass_box:
                turn.glass_box.append(entry)
            turn.state = turn.state.advance(rules_applied=[*turn.state.rules_applied, decision.rule])
        return evaluation

    def _detail(self, turn: Turn, n: int | None) -> ChargeDetail | None:
        if n is None:
            return None
        detail = self._tools.view_charge(turn.session, self._offers(turn), ViewChargeInput(candidate_n=n))
        if isinstance(detail, ToolError):
            return None
        turn.amounts.add(money(detail.amount, detail.currency))
        return detail

    def _receipt(self, turn: Turn, charge: Candidate) -> str:
        language = language_of(turn.state.variant)
        when = f"{day(charge.occurred_at.date(), language)}, {charge.occurred_at:%H:%M}"
        # Bank adjustments never carry a merchant, and a few purchases lack one: the receipt names the kind instead.
        label = charge.merchant or self._text(turn, f"unnamed_{charge.kind.value}")
        place = ", ".join(part for part in (label, charge.city) if part)
        amount = money(charge.amount, charge.currency)
        turn.amounts.add(amount)
        status = status_word(charge.status, language)
        return self._text(turn, "receipt", date=when, merchant=place, amount=amount, status=status)

    def _money(self, turn: Turn, value: Money) -> str:
        text = money(value.amount, value.currency)
        turn.amounts.add(text)
        return text

    def _charge_in_question(self, turn: Turn) -> ChargeSummary | None:
        state = turn.state
        n = state.chosen if state.chosen is not None else next(iter(state.disputed), None)
        detail = self._detail(turn, n)
        if detail is None:
            return None
        return ChargeSummary(
            merchant=detail.merchant,
            city=detail.city,
            amount=detail.amount,
            currency=detail.currency,
            occurred_at=detail.occurred_at,
            status=detail.status,
            card=detail.card,
        )

    def _case_cards(self, turn: Turn) -> list[str]:
        details = [self._detail(turn, n) for n in turn.state.disputed]
        return [d.card for d in details if d is not None and d.card]

    def _actions(self, turn: Turn) -> tuple[Action, ...]:
        events = self._log.read(turn.session.conversation_id)
        actions = []
        for event in events:
            if event.type is EventType.ACTION_READ_BACK and event.data.get("tool") in (
                "block_card",
                "register_dispute",
            ):
                actions.append(
                    Action(
                        action=event.data["tool"], result="ok" if event.data["matches"] else "failed", read_back=True
                    )
                )
        return tuple(actions)

    def _offers(self, turn: Turn) -> Offers:
        return Offers(charges=dict(turn.state.charges_offered), cards=dict(turn.state.cards_offered))

    def _country(self, turn: Turn) -> Country:
        return self._tools.customer(turn.session).country

    def _text(self, turn: Turn, name: str, **values: object) -> str:
        return self._renderer.text(name, turn.state.variant, **values)

    def _yes_no(self, turn: Turn) -> None:
        yes, no = YES_NO[language_of(turn.state.variant)]
        turn.options.extend([Option(n=1, label=yes, answer="yes"), Option(n=2, label=no, answer="no")])

    def _ask_again(self, turn: Turn, template: str, step: Step | None = None) -> None:
        """POL-05: the same question again, or one more detail, at most three times; then a person."""
        attempts = turn.state.attempts + 1
        evaluation = self._evaluate(
            turn,
            Facts(account_country=self._country(turn), candidates_found=0, question_attempts=attempts),
        )
        if evaluation.escalate:
            turn.lines.append(self._text(turn, "handoff_unclear"))
            self._hand_off(turn, evaluation.queue or Queue.COMPLAINTS, TransferReason.NOT_UNDERSTOOD)
            return
        turn.lines.append(self._text(turn, template, pick=attempts - 1))
        if step in (None, turn.state.step):
            self._show_again(turn)
        turn.state = turn.state.advance(attempts=attempts, step=step or turn.state.step)

    def _repeat_question(self, turn: Turn) -> None:
        """The open question is asked again with its options, so a message on the side does not cut the flow."""
        if turn.state.step is Step.ASK_CLAIM:
            turn.lines.append(self._text(turn, "ask_claim_again"))
        elif turn.state.step is Step.SCAM_DETAILS:
            turn.lines.append(self._text(turn, "scam_again"))
        elif turn.asked and turn.asked.data.get("options"):
            turn.lines.append(self._text(turn, "back_to_question"))
            self._show_again(turn)

    def _show_again(self, turn: Turn) -> None:
        """The options and the pending confirmation of the previous reply are offered again."""
        shown = turn.asked.data if turn.asked else {}
        turn.options.extend(Option.model_validate(option) for option in shown.get("options", []))
        turn.multiple_choice = turn.state.step is Step.SWEEP and bool(turn.options)
        if shown.get("pending"):
            turn.pending = PendingConfirmation.model_validate(shown["pending"])

    def _alert_fraud_if_due(self, turn: Turn) -> None:
        """POL-16: when the dispute part ends, with or without a case, the Fraud team gets one alert."""
        state = turn.state
        if not state.fraud_alert_charges or state.fraud_alert_id or state.step not in (Step.DONE, Step.HANDED_OFF):
            return
        args = SendFraudAlertInput(
            charges_n=tuple(state.fraud_alert_charges),
            signals=tuple(signal.value for signal in state.signals),
            card_blocked=any(a.action == "block_card" and a.result == "ok" for a in self._actions(turn)),
            case_id=state.case_id,
        )
        result = self._tools.send_fraud_alert(turn.session, self._offers(turn), args)
        self._record_tool(turn, "send_fraud_alert", args.model_dump(mode="json"), result.output)
        if isinstance(result.output, ToolError):
            # POL-13: a person follows up; the next turn tries the alert again.
            if state.step is not Step.HANDED_OFF:
                self._fail(turn)
            return
        alert_id = result.output.alert_id
        self._record(turn, EventType.FRAUD_ALERT, {"alert_id": alert_id, **args.model_dump(mode="json")})
        turn.state = turn.state.advance(fraud_alert_id=alert_id)

    def _fail(self, turn: Turn) -> None:
        """POL-13: a failed tool or a read-back that does not match goes to a person; nothing is filled in."""
        self._evaluate(
            turn, Facts(account_country=self._country(turn), tool_failed=True, already_escalated=turn.state.escalated)
        )
        turn.lines.append(self._text(turn, "tool_failure"))
        self._hand_off(turn, Queue.COMPLAINTS, TransferReason.TOOL_FAILURE)

    def _hand_off(self, turn: Turn, queue: Queue, reason: TransferReason) -> None:
        """A person takes over, and the analyst gets a note with what is already known (POL-01)."""
        transfer_id = self._leave_note(turn, queue, reason)
        data = {"case_id": turn.state.case_id, "queue": queue.value, "transfer_id": transfer_id}
        self._record(turn, EventType.HANDOFF, data)
        turn.state = turn.state.advance(step=Step.HANDED_OFF, escalated=True, queue=queue)

    def _leave_note(self, turn: Turn, queue: Queue, reason: TransferReason) -> str | None:
        """The transfer note; when it cannot be built or kept, the conversation still goes to the person."""
        args = CreateTransferInput(queue=queue, reason=reason)
        try:
            note = self._transfer_note(turn, queue, reason)
        except ValueError:
            self._record_tool(turn, "create_transfer", args.model_dump(mode="json"), INVALID_NOTE)
            return None
        result = self._tools.create_transfer(turn.session, args, note)
        self._record_tool(turn, "create_transfer", args.model_dump(mode="json"), result.output)
        return None if isinstance(result.output, ToolError) else result.output.transfer_id

    def _transfer_note(self, turn: Turn, queue: Queue, reason: TransferReason) -> Transfer:
        state = turn.state
        known = state.disputed or ([state.chosen] if state.chosen is not None else sorted(state.charges_offered))
        signals = tuple(sorted(s.value for s in state.signals if s is not Signal.NEW_MERCHANT))
        return build_transfer(
            reason=reason,
            customer=self._tools.customer(turn.session),
            variant=state.variant,
            claim_type=state.claim_type,
            charges=tuple(d for d in (self._detail(turn, n) for n in known) if d is not None),
            declared=DeclaredFacts(
                channel=state.declared_channel,
                has_card=state.has_card,
                authorized_payment=state.authorized_payment,
                date_text=state.date_text,
                contacted_by=state.contacted_by,
            ),
            actions=self._actions(turn),
            pending_action=state.pending_tool,
            case_id=state.case_id,
            risk_signals=signals,
            fraud_alert=bool(state.fraud_alert_charges),
            rules_applied=tuple(dict.fromkeys(state.rules_applied)),
            queue=queue,
            policy_version=self._engine.version,
            conversation_id=turn.session.conversation_id,
            created_at=_aware(self._now()),
        )

    def _record(
        self, turn: Turn, event_type: EventType, data: dict[str, JsonValue], provider: str | None = None
    ) -> None:
        event = new_event(
            turn.last_event,
            turn.session.conversation_id,
            event_type,
            data,
            now=lambda: _aware(self._now()),
            new_id=self._new_id,
            llm_provider=provider,
        )
        self._log.append(event)
        turn.last_event = event

    def _record_tool(self, turn: Turn, tool: str, arguments: dict, result: object) -> None:
        self._record(turn, EventType.TOOL_CALLED, {"tool": tool, "arguments": arguments})
        outcome = result.code.value if isinstance(result, ToolError) else "ok"
        self._record(turn, EventType.TOOL_RESULT, {"tool": tool, "result": outcome})

    def _record_write(self, turn: Turn, tool: str, args: object, output: object, matches: bool) -> None:
        key = args.confirmation_token
        self._record(turn, EventType.CONFIRMATION, {"tool": tool, "idempotency_key": key})
        self._record(turn, EventType.TOOL_CALLED, {"tool": tool, "idempotency_key": key})
        result = output.code.value if isinstance(output, ToolError) else "ok"
        self._record(turn, EventType.TOOL_RESULT, {"tool": tool, "result": result})
        self._record(turn, EventType.ACTION_READ_BACK, {"tool": tool, "idempotency_key": key, "matches": matches})

    def _finish(self, turn: Turn) -> MessageResponse:
        text = "\n\n".join(turn.lines)
        previous = turn.asked.data.get("text") if turn.asked else None
        if text == previous and turn.state.step not in (Step.DONE, Step.HANDED_OFF):
            # The same words twice in a row read as a machine stuck: the reply is introduced differently.
            text = f"{self._text(turn, 'rephrase', pick=turn.state.attempts)} {text}"
        try:
            text = check(text, frozenset(turn.amounts))
        except UnsafeReplyError as error:
            self._record(turn, EventType.RULE_DECISION, {"rule": "output_validator", "violations": error.violations})
            text = self._text(turn, "tool_failure")
            turn.state = turn.state.advance(step=Step.HANDED_OFF, escalated=True)
            turn.options.clear()
        response = MessageResponse(
            reply=text,
            options=tuple(turn.options),
            multiple_choice=turn.multiple_choice,
            pending_confirmation=turn.pending,
            glass_box=tuple(turn.glass_box),
            stage=_stage(turn.state),
            charge=self._charge_in_question(turn),
            case_id=turn.state.case_id,
        )
        self._record(
            turn,
            EventType.REPLY,
            {
                "text": text,
                "options": [o.model_dump(mode="json") for o in turn.options],
                "pending": turn.pending.model_dump(mode="json") if turn.pending else None,
                "state": turn.state.model_dump(mode="json"),
            },
        )
        return response


def _stage(state: FlowState) -> Stage:
    if state.step is Step.ASK_CLAIM:
        return "analysis" if state.claim_type else "received"
    return STAGES.get(state.step, "verification")


def _no_results(result: object) -> bool:
    """The search ran and found nothing, which is not the same as a search that failed."""
    return isinstance(result, ToolError) and result.code is ToolErrorCode.NO_RESULTS


def _aside(reading: Interpretation) -> bool:
    """A message about something else that answers nothing of the open question."""
    return (
        reading.claim_type is ClaimType.OUT_OF_SCOPE
        and reading.answer is Answer.NOT_SAID
        and not reading.selected_numbers
    )


def _exposure(details: list[ChargeDetail]) -> tuple[Money, ...]:
    totals: dict = {}
    for detail in details:
        totals[detail.currency] = totals.get(detail.currency, Decimal(0)) + detail.amount
    return tuple(Money(amount=amount, currency=currency) for currency, amount in sorted(totals.items()))


def _charges(turn: Turn, count: int) -> str:
    singular, plural = ("cobrança", "cobranças") if turn.state.variant is LanguageVariant.PT else ("cargo", "cargos")
    return f"{count} {singular if count == 1 else plural}"


def _overrides_the_button(reading: Interpretation) -> bool:
    """A person, a threat or a question about who answers in the text wins over the button (POL-01, POL-02)."""
    return reading.claim_type is ClaimType.HUMAN_REQUEST or reading.coercion or reading.asks_if_human


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.astimezone()


def _venue(country: Country) -> str:
    return {Country.CO: "la Superintendencia Financiera", Country.MX: "la CONDUSEF", Country.AR: "el BCRA"}[country]
