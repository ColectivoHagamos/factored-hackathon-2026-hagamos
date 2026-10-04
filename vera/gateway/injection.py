"""Signals of prompt injection or of a request for another customer's data, read on the original text.

They do not try to understand the message: a signal only makes the flow treat it as data (POL-03), act on nothing
and record a security event. The patterns are narrow on purpose, because a customer who says that someone else used
the card is making a claim, not an attack. A message that slips through still meets the closed interpreter schema
and the action gate.
"""

import re
import unicodedata

PATTERNS = {
    "instruction_override": re.compile(
        r"\b(ignora|ignore|ignorar|olvida|olvidate|omite|esquece|esqueca|desconsidera|disregard|forget)\b.{0,40}"
        r"\b(instrucciones|instruccion|instrucoes|instrucao|instructions|reglas|regla|regras|regra|rules|politica)"
    ),
    "role_change": re.compile(
        r"\b(ahora eres|eres ahora|a partir de ahora eres|finge ser|finge que eres|haz de cuenta que eres|"
        r"actua como si fueras|modo desarrollador|modo administrador|modo sin restricciones|developer mode|jailbreak|"
        r"agora voce e|voce agora e|finja ser|finja que e|aja como se fosse|you are now|pretend to be)\b"
    ),
    "system_prompt": re.compile(
        r"\b(system prompt|prompt del sistema|prompt de sistema|prompt do sistema|tu prompt|seu prompt|your prompt|"
        r"instrucciones internas|instrucoes internas|mensaje del sistema|mensagem do sistema)\b"
    ),
    "other_customer": re.compile(
        r"\b(otro|otra|otros|otras|outro|outra|outros|outras) (cliente|clientes)\b"
        r"|\bcliente (con|com) (documento|cedula|dni|curp|rfc|cuit|cpf)\b"
        r"|\bcus-[a-z0-9]{6,}\b"
    ),
    "tool_syntax": re.compile(
        r"\{\s*\"(tool|function|action|name)\"\s*:|<\s*/?\s*(system|tool|assistant)\s*>|\bfunction_call\b"
    ),
}


def fold(text: str) -> str:
    """Lowercase without accents, so «Ignorá» and «ignora» read the same."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def signals(original_text: str) -> tuple[str, ...]:
    """Names of the patterns found in the text, in a fixed order."""
    folded = fold(original_text)
    return tuple(name for name, pattern in PATTERNS.items() if pattern.search(folded))
