"""Deterministic simulated customer (P44): it talks to VERA over HTTP, in process, and only answers what is asked.

It reads the screen the way a customer would: it picks the option whose receipt is its charge, says whether it has
the card, accepts or declines the block, and confirms. Run k of a case uses wording variant k of every phrase.
It never volunteers anything and never sees the policy; whether the outcome is right is up to the graders.
"""

import os
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

CARD_QUESTION = re.compile(r"tarjeta con|cartão está com")
RECOGNIZE_QUESTION = re.compile(r"[Rr]econoc|reconhece")
IS_THIS_THE_CHARGE = re.compile(r"Es este el cobro|É esta a cobrança")
# POL-10: the key questions of a scam, asked in free text.
SCAM_QUESTION = re.compile(r"cuándo fue la transferencia|quando foi a transferência")
PERSON_OFFER = re.compile(r"pase con una persona|passe a conversa para uma pessoa")
# POL-01 (v1.5): before the transfer a customer asked for, VERA offers once to review the case first.
REVIEW_FIRST = re.compile(r"conectar con un analista|conectar você com um analista")
BACK_TO_QUESTION = re.compile(r"pregunta anterior|pergunta anterior")
MAX_TURNS = 14
START = datetime.combine(load_policy().parameters.system_clock, datetime.min.time()).replace(hour=10)


def load_phrases(which: str) -> dict:
    """The wordings of a set: the development set and the sealed held-out never share one."""
    path = Path(__file__).parent / f"phrases_{which}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))["templates"]


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
    # Times VERA asked in free text and the customer had to explain again: the effort a misreading costs.
    explained_again: int = 0


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


def phrase(phrases: dict, name: str, language: str, variant: int, **values: str) -> str:
    """The wording, with only the known placeholders filled: a phrase may itself contain braces, as JSON does."""
    text = phrases[name][language][variant]
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


class Customer:
    def __init__(
        self, case: Case, variant: int, interpreter: str, demo_db: Path, charges: Charges, phrases: dict
    ) -> None:
        self.case, self.variant, self.charges, self.phrases = case, variant, charges, phrases
        self.clock = Clock()
        settings = Settings(
            adapter="dataset",
            demo_db=str(demo_db),
            llm=interpreter,
            session_secret="evaluation",
            messages_per_minute=10_000,
            # Only Claude uses them; the key never leaves the environment.
            llm_api_key=os.environ.get("LLM_API_KEY", ""),
            llm_workspace_id=os.environ.get("LLM_WORKSPACE_ID", ""),
        )
        factory = (lambda state: UnavailableTransactions(demo_db, state)) if case.script.tools_fail else None
        self.container: Container = build(settings, now=self.clock, bank_factory=factory)
        self.client = TestClient(create_app(settings, self.container), raise_server_exceptions=False)
        self.transcript = Transcript(case.id, variant)
        self.asked_for_a_person = False
        self.answered_the_scam_questions = False
        self.free_text_questions = 0
        # The last question VERA asked, to answer it again when VERA comes back to it after a detour.
        self.open_question = ""

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

    def values(self) -> dict[str, str]:
        case, values = self.case, {}
        if case.target:
            values["merchant"] = self.charges.merchant(case.target[0]) or ""
        if case.wrong_merchant_from:
            values["wrong_merchant"] = self.charges.merchant(case.wrong_merchant_from)
        if case.other_customer:
            values["other"] = case.other_customer
        return values

    def opening(self) -> str:
        return phrase(self.phrases, self.case.script.opening, self.case.language, self.variant, **self.values())

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
            if mine:
                return {"selected_option": mine["n"]}
            return {"text": phrase(self.phrases, "none_of_these", language, variant)}
        text = reply["reply"]
        if BACK_TO_QUESTION.search(text):
            text = self.open_question
        elif not (REVIEW_FIRST.search(text) or PERSON_OFFER.search(text)):
            self.open_question = text
        if options and CARD_QUESTION.search(text):
            return {"selected_option": "yes" if script.has_card else "no"}
        if options and "internet" in text:
            return {"selected_option": "yes"}
        if options and RECOGNIZE_QUESTION.search(text):
            if script.asks_for_a_person_at_receipt and not self.asked_for_a_person:
                self.asked_for_a_person = True
                return {"text": phrase(self.phrases, "human_midflow", language, variant)}
            return {"selected_option": "yes" if script.recognizes_after_receipt else "no"}
        if options and PERSON_OFFER.search(text):
            return {"selected_option": "yes" if self.case.block == "human" else "no"}
        if options and REVIEW_FIRST.search(text):
            # A customer who asked for a person insists; anyone else lets VERA review the case first.
            return {"selected_option": "no" if self.case.block == "human" else "yes"}
        if options and IS_THIS_THE_CHARGE.search(text):
            mine = self.case.target and self.charges.shown_in(self.case.target[0], text)
            return {"selected_option": "yes" if mine else "no"}
        if options:
            return {"selected_option": "yes"}
        if SCAM_QUESTION.search(text) and "scam_answer" in self.phrases and not self.answered_the_scam_questions:
            # The development set has the answer; a held-out run, sealed before scams, goes on as below.
            self.answered_the_scam_questions = True
            return {"text": phrase(self.phrases, "scam_answer", language, variant)}
        # A question in free text: the customer gives the merchant once, then tells its claim in other words twice,
        # and then leaves, as a customer who is not understood would.
        self.free_text_questions += 1
        self.transcript.explained_again = self.free_text_questions
        known = self.case.target[0] if self.case.target else self.case.wrong_merchant_from
        if self.free_text_questions == 1 and known and self.charges.merchant(known):
            merchant = self.charges.merchant(known)
            return {"text": phrase(self.phrases, "detail", language, variant, merchant=merchant)}
        if self.free_text_questions <= 3:
            wording = (variant + self.free_text_questions) % 3
            return {"text": phrase(self.phrases, self.case.script.opening, language, wording, **self.values())}
        return None
