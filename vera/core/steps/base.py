"""What every step of the flow shares: the turn being built, the dependencies, and the helpers that read the
tools, cite the rules and record the events."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from pydantic import JsonValue

from vera.contracts.cases import Case
from vera.contracts.charges import Candidate, ChargeDetail, ChargeKind, ChargeStatus
from vera.contracts.common import Country, Language, Money
from vera.contracts.conversation import ChargeSummary, GlassBoxEntry, Option, PendingConfirmation
from vera.contracts.events import Event, EventType
from vera.contracts.handoff import Action, LanguageVariant, Queue, TransferReason
from vera.contracts.interpretation import Answer, ClaimType, Interpretation
from vera.contracts.tools import ToolError, ToolErrorCode, ViewChargeInput
from vera.core.events import new_event
from vera.core.state import FlowState, Step
from vera.output.render import Renderer, day, language_of, money, status_word
from vera.policy.engine import Evaluation, Facts, Outcome, PolicyEngine, exposure_usd
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


class FlowSupport:
    """The dependencies of the flow and what its steps share; each group of steps builds on it."""

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

    def _dispute_facts(self, turn: Turn, details: list[ChargeDetail], case: Case | None = None) -> Facts:
        exposure = (
            case.total_exposure if case else exposure_of([d for d in details if d.status is ChargeStatus.APPROVED])
        )
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

    def _reference(self, turn: Turn, charge: Candidate) -> str:
        """The charge as a person names it in a sentence: what, how much, and the day and time."""
        language = language_of(turn.state.variant)
        amount = money(charge.amount, charge.currency)
        turn.amounts.add(amount)
        when = {"date": day(charge.occurred_at.date(), language), "time": f"{charge.occurred_at:%H:%M}"}
        if not charge.merchant:
            return self._text(turn, f"charge_{charge.kind.value}", amount=amount, **when)
        place = f"{charge.merchant} ({charge.city})" if charge.city else charge.merchant
        return self._text(turn, "charge_named", merchant=place, amount=amount, **when)

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
        pick = attempts - 1
        previous = turn.asked.data.get("text", "") if turn.asked else ""
        if self._text(turn, template, pick=pick) in previous:
            # A question asked again comes back in other words when the template has them.
            pick += 1
        turn.lines.append(self._text(turn, template, pick=pick))
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

    def _record(
        self, turn: Turn, event_type: EventType, data: dict[str, JsonValue], provider: str | None = None
    ) -> None:
        event = new_event(
            turn.last_event,
            turn.session.conversation_id,
            event_type,
            data,
            now=lambda: aware(self._now()),
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


def no_results(result: object) -> bool:
    """The search ran and found nothing, which is not the same as a search that failed."""
    return isinstance(result, ToolError) and result.code is ToolErrorCode.NO_RESULTS


def is_aside(reading: Interpretation) -> bool:
    """A message about something else that answers nothing of the open question."""
    return (
        reading.claim_type is ClaimType.OUT_OF_SCOPE
        and reading.answer is Answer.NOT_SAID
        and not reading.selected_numbers
    )


def exposure_of(details: list[ChargeDetail]) -> tuple[Money, ...]:
    totals: dict = {}
    for detail in details:
        totals[detail.currency] = totals.get(detail.currency, Decimal(0)) + detail.amount
    return tuple(Money(amount=amount, currency=currency) for currency, amount in sorted(totals.items()))


def charges_text(turn: Turn, count: int) -> str:
    singular, plural = ("cobrança", "cobranças") if turn.state.variant is LanguageVariant.PT else ("cargo", "cargos")
    return f"{count} {singular if count == 1 else plural}"


def overrides_the_button(reading: Interpretation) -> bool:
    """A person, a threat or a question about who answers in the text wins over the button (POL-01, POL-02)."""
    return reading.claim_type is ClaimType.HUMAN_REQUEST or reading.coercion or reading.asks_if_human


def aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.astimezone()


def venue_of(country: Country) -> str:
    return {Country.CO: "la Superintendencia Financiera", Country.MX: "la CONDUSEF", Country.AR: "el BCRA"}[country]
