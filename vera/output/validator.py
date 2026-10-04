"""Output validator: every reply passes here before it reaches the customer.

It blocks links, requests for secrets, promises about money, blame, claims of being human, conclusions reserved
to judges, and any amount that did not come from a tool.
"""

import re

FORBIDDEN: dict[str, str] = {
    "link": r"https?://|www\.|\b[\w-]+\.(com|co|mx|ar|net|org|io)\b",
    "secret_request": r"\b(otp|pin|cvv|cvc|contrase[ñn]a|senha|clave de seguridad|c[oó]digo de verificaci[oó]n|"
    r"n[uú]mero completo de (la|su|tu) tarjeta)\b",
    "money_promise": r"\b(te|le|lo|la|vamos a|vamos)?\s*(devolveremos|reembolsaremos|devolvemos|reembolsamos|"
    r"garantizamos|garantimos|vamos devolver|reembolso garantizado|seguro que (te|le) devuelven)\b",
    "blame": r"\b(fue (tu|su) culpa|es (tu|su) responsabilidad|(usted|tú|vos) autoriz[oó]|autorizaste|"
    r"a culpa (foi|é) sua|voc[eê] autorizou)\b",
    "human_claim": r"\b(soy (una )?persona( real)?|soy human[oa]|sou (uma )?pessoa|sou human[oa])\b",
    # PROH-01: only judges may conclude that there was no impersonation.
    "impersonation_conclusion": r"\b(no hubo suplantaci[oó]n|n[aã]o houve fraude|no fue fraude|n[aã]o foi fraude)\b",
}
AMOUNT = re.compile(r"\b(USD|COP|ARS) \d{1,3}(?:\.\d{3})*(?:,\d{2})?\b")


class UnsafeReplyError(ValueError):
    def __init__(self, violations: list[str]) -> None:
        super().__init__(f"reply blocked by the output validator: {', '.join(violations)}")
        self.violations = violations


def violations(reply: str, allowed_amounts: frozenset[str] = frozenset()) -> list[str]:
    """Names of the rules the reply breaks; an empty list means the reply can be sent."""
    found = [name for name, pattern in FORBIDDEN.items() if re.search(pattern, reply, re.IGNORECASE)]
    if any(match.group(0) not in allowed_amounts for match in AMOUNT.finditer(reply)):
        found.append("amount_not_from_tools")
    return found


def check(reply: str, allowed_amounts: frozenset[str] = frozenset()) -> str:
    """Return the reply if it is safe; raise UnsafeReplyError otherwise."""
    problems = violations(reply, allowed_amounts)
    if problems:
        raise UnsafeReplyError(problems)
    return reply
