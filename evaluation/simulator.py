"""Deterministic simulated customer (P44): it talks to VERA over HTTP, in process, and only answers what is asked.

It reads the screen the way a customer would: it picks the option whose receipt is its charge, says whether it has
the card, accepts or declines the block, and confirms. Run k of a case uses wording variant k of every phrase.
It never volunteers anything and never sees the policy; whether the outcome is right is up to the graders.
"""

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import yaml
from fastapi.testclient import TestClient

from api.dependencies import Container, build
from api.main import create_app
from api.settings import Settings
from evaluation.cases import Case
from vera.adapters.demo_bank import DemoBank
from vera.contracts.common import Currency
from vera.core.state import FlowState, Step
from vera.output.render import money
from vera.policy.model import load_policy

PHRASES = yaml.safe_load((Path(__file__).parent / "phrases.yaml").read_text(encoding="utf-8"))["templates"]
CARD_QUESTION = re.compile(r"tarjeta con|cartão está com")
RECOGNIZE_QUESTION = re.compile(r"[Rr]econoc|reconhece")
IS_THIS_THE_CHARGE = re.compile(r"Es este el cobro|É esta a cobrança")
MAX_TURNS = 14
START = datetime.combine(load_policy().parameters.system_clock, datetime.min.time()).replace(hour=10)


class Clock:
    def __init__(self) -> None:
        self.moment = START

    def __call__(self) -> datetime:
        return self.moment


class UnavailableTransactions(DemoBank):
    """The transactions store does not answer: every read of charges times out."""

    def charges(self, customer_ref, since, until):
        raise TimeoutError("the transactions store did not answer")


@dataclass
class Transcript:
    case_id: str
    variant: int
    turns: list[tuple[dict, dict]] = field(default_factory=list)
    statuses: list[int] = field(default_factory=list)
    most_candidates_listed: int = 0
    session_expired: bool = False
    seconds_per_turn: list[float] = field(default_factory=list)


class Charges:
    """Receipt facts of the demo subset, read once, so the customer can recognize its own charge on screen."""

    def __init__(self, demo_db: Path) -> None:
        con = duckdb.connect(str(demo_db), read_only=True)
        rows = con.execute("SELECT charge_ref, merchant, amount, currency, occurred_at FROM charges").fetchall()
        self.by_ref = {
            ref: (merchant, amount, currency, occurred_at) for ref, merchant, amount, currency, occurred_at in rows
        }

    def merchant(self, ref: str) -> str:
        return self.by_ref[ref][0]

    def shown_in(self, ref: str, label: str) -> bool:
        merchant, amount, currency, occurred_at = self.by_ref[ref]
        pieces = (money(amount, Currency(currency)), f"{occurred_at:%H:%M}", merchant or "Ajuste")
        return all(piece in label for piece in pieces)


def phrase(name: str, language: str, variant: int, **values: str) -> str:
    """The wording, with only the known placeholders filled: a phrase may itself contain braces, as JSON does."""
    text = PHRASES[name][language][variant]
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


class Customer:
    def __init__(self, case: Case, variant: int, interpreter: str, demo_db: Path, charges: Charges) -> None:
        self.case, self.variant, self.charges = case, variant, charges
        self.clock = Clock()
        settings = Settings(
            adapter="dataset",
            demo_db=str(demo_db),
            llm=interpreter,
            session_secret="evaluation",
            messages_per_minute=10_000,
        )
        factory = (lambda state: UnavailableTransactions(demo_db, state)) if case.script.tools_fail else None
        self.container: Container = build(settings, now=self.clock, bank_factory=factory)
        self.client = TestClient(create_app(settings, self.container), raise_server_exceptions=False)
        self.transcript = Transcript(case.id, variant)
        self.asked_for_a_person = False

    def talk(self) -> Transcript:
        token = self.client.post("/v1/demo-session", json={"demo_customer": self.case.customer}).json()["token"]
        self.headers = {"Authorization": f"Bearer {token}"}
        self.conversation = self.client.post("/v1/conversations", json={}, headers=self.headers).json()[
            "conversation_id"
        ]
        message = {"text": self.opening()}
        for _ in range(MAX_TURNS):
            reply = self.send(message)
            if reply is None or self.finished():
                break
            message = self.answer(reply)
            if message is None:
                break
        return self.transcript

    def opening(self) -> str:
        case, values = self.case, {}
        if case.target:
            values["merchant"] = self.charges.merchant(case.target[0]) or ""
        if case.wrong_merchant_from:
            values["wrong_merchant"] = self.charges.merchant(case.wrong_merchant_from)
        if case.other_customer:
            values["other"] = case.other_customer
        return phrase(case.script.opening, case.language, self.variant, **values)

    def send(self, message: dict) -> dict | None:
        started = time.perf_counter()
        response = self.client.post(
            f"/v1/conversations/{self.conversation}/messages", json=message, headers=self.headers
        )
        self.transcript.seconds_per_turn.append(time.perf_counter() - started)
        self.transcript.statuses.append(response.status_code)
        if response.status_code == 401:
            self.transcript.session_expired = True
            return None
        if response.status_code != 200:
            return None
        reply = response.json()
        self.transcript.turns.append((message, reply))
        candidates = [o for o in reply["options"] if not o.get("answer")]
        self.transcript.most_candidates_listed = max(self.transcript.most_candidates_listed, len(candidates))
        return reply

    def finished(self) -> bool:
        events = self.container.conversation.history(self.conversation)
        reply = next(e for e in reversed(events) if e.type == "reply")
        return FlowState.model_validate(reply.data["state"]).step in (Step.DONE, Step.HANDED_OFF)

    def answer(self, reply: dict) -> dict | None:
        script, language, variant = self.case.script, self.case.language, self.variant
        pending = (reply.get("pending_confirmation") or {}).get("action")
        options = reply["options"]
        if pending == "register_dispute":
            if script.session_expires_before_confirming:
                # The customer leaves the confirmation open longer than the session lives.
                self.clock.moment += timedelta(minutes=16)
            return {"selected_option": "yes"}
        if pending == "block_card":
            return {"selected_option": "yes" if script.accepts_block else "no"}
        if reply.get("multiple_choice"):
            return {"text": "todos"}
        if options and not any(o.get("answer") for o in options):
            mine = next(
                (o for o in options if self.case.target and self.charges.shown_in(self.case.target[0], o["label"])),
                None,
            )
            return {"selected_option": mine["n"]} if mine else {"text": phrase("none_of_these", language, variant)}
        text = reply["reply"]
        if options and CARD_QUESTION.search(text):
            return {"selected_option": "yes" if script.has_card else "no"}
        if options and "internet" in text:
            return {"selected_option": "yes"}
        if options and RECOGNIZE_QUESTION.search(text):
            if script.asks_for_a_person_at_receipt and not self.asked_for_a_person:
                self.asked_for_a_person = True
                return {"text": phrase("human_midflow", language, variant)}
            return {"selected_option": "yes" if script.recognizes_after_receipt else "no"}
        if options and IS_THIS_THE_CHARGE.search(text):
            mine = self.case.target and self.charges.shown_in(self.case.target[0], text)
            return {"selected_option": "yes" if mine else "no"}
        if options:
            return {"selected_option": "yes"}
        # A question in free text: the customer can only repeat what it knows about its charge.
        known = self.case.target[0] if self.case.target else self.case.wrong_merchant_from
        if known and self.charges.merchant(known):
            return {"text": phrase("detail", language, variant, merchant=self.charges.merchant(known))}
        return None
