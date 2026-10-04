"""Rules interpreter: keyword patterns in Spanish and Portuguese.

It is the baseline the challenge asks for and the fallback when the language model is unavailable. It returns the
same closed schema as any model adapter, and a low confidence when nothing matches, so the flow asks instead of acting.
"""

import re
import unicodedata
from decimal import Decimal

from vera.contracts.common import Currency, Language
from vera.contracts.interpretation import Answer, ClaimType, DeclaredChannel, Interpretation


def _fold(text: str) -> str:
    """Lower case without accents, so patterns are written once for both spellings."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _any(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


PORTUGUESE = (
    r"\bnao\b",
    r"\bvoce\b",
    r"\bcartao\b",
    r"\bcobranca\b",
    r"\bobrigad",
    r"\breconheco\b",
    r"\bminha\b",
    r"\bontem\b",
    r"\bestou\b",
    r"\bfiz\b",
    r"\bfalar com\b",
    r"\bpessoa\b",
    r"\bum\b",
    r"\buma\b",
    r"\bnunca fiz\b",
    r"\b(quero|minhas|meus|voces|faturas?|endereco|tambem|ajuda|pode|posso|poupanca|emprestimo|gostaria|aplicativo)\b",
)
HUMAN = (
    r"\b(una persona|un humano|humano|un asesor|asesor|agente humano|alguien real|operador|una persona real)\b",
    r"\b(uma pessoa|atendente|falar com alguem|pessoa de verdade)\b",
)
COERCION = (
    r"\b(me amenaz|amenazad|me obligan|me estan obligando|secuestr|extorsi|me tienen retenid|me apuntan)",
    r"\b(ameaca|me obrigam|me obrigando|sequestr|extorsao)",
)
REGULATOR = (
    r"\b(condusef|superintendencia|superfinanciera|sfc|bcra|defensor del consumidor|defensoria|procon)\b",
    r"\b(banco central|denunciar ante|ir al regulador|demandar)\b",
)
PIX = (r"\bpix\b",)
SCAM = (
    r"\b(me enganaron|estafa|estafaron|me estafaron|hice una transferencia|transferi|deposite a|golpe|me enganaram)",
    r"\b(fraude telefonic|me llamaron del banco|me pidieron la clave)",
)
IMPROPER = (
    r"\b(cobro indebido|me cobraron (una |un )?(comision|cuota|cargo del banco|seguro)|cuota de manejo|ajuste)",
    r"\b(cobrado dos veces|cobro duplicado|me cobraron de mas|monto incorrecto|cobranca indevida|tarifa)",
)
UNRECOGNIZED = (
    r"\b(no reconozco|desconozco|no la hice|no hice (esa|esta|ese|este)|no fui yo|cargo que no|compra que no)",
    r"\b(no autorice|(cargo|cobro|movimiento|compra|algo) (raro|rara|extrano|extrana|sospechoso|sospechosa))",
    r"\b(nao reconheco|nao fiz|nao fui eu|nao reconheco essa|desconheco|nao autorizei)",
    r"\b(cobranca|compra|movimento|algo) (estranh|suspeit)",
)
OUT_OF_SCOPE = (
    r"\b(saldo|balance|extracto|prestamo|abrir una cuenta|credito hipotecario|tasa de interes)\b",
    r"\b(cuanto debo|pago minimo|fecha de corte|fecha de pago|limite de credito|cupo disponible)\b",
    r"\b(meu saldo|extrato|emprestimo|quanto devo|pagamento minimo|limite do cartao)\b",
)
ONLINE = (r"\b(internet|en linea|online|por la app|en la app|pagina web|sitio web|pela internet|on line)\b",)
IN_PERSON = (r"\b(presencial|en la tienda|en el local|en persona|datafono|na loja|pessoalmente)\b",)
NO_CARD = (
    r"\b(no tengo la tarjeta|no la tengo|me la robaron|me robaron|perdi la tarjeta|la perdi|se me perdio)\b",
    r"\b(nao tenho o cartao|roubaram|perdi o cartao|furtaram)\b",
)
HAS_CARD = (r"\b(tengo la tarjeta|la tengo conmigo|esta conmigo|la tengo aqui|tenho o cartao|esta comigo)\b",)
YES = (r"^\s*(si|sim|claro|correcto|ok|dale|de acuerdo|confirmo|exacto|afirmativo|isso)\b",)
NO = (r"^\s*(no|nao|nunca|negativo|para nada)\b",)
EMPTY_NOUNS = {"El", "La", "Los", "Las", "Un", "Una", "Mi", "Me", "Que", "Hola", "Buenas", "Ayer", "Hoy", "O", "A"}
CURRENCY_WORDS = {
    "usd": Currency.USD,
    "dolares": Currency.USD,
    "dollars": Currency.USD,
    "us$": Currency.USD,
    "cop": Currency.COP,
    "ars": Currency.ARS,
}
DATE_PATTERN = (
    r"\b(ayer|anteayer|antier|hoy|esta semana|la semana pasada|el (lunes|martes|miercoles|jueves|viernes|"
    r"sabado|domingo)|hace \d+ dias|ontem|hoje|anteontem|\d{1,2} de [a-z]+|\d{1,2}/\d{1,2}(/\d{2,4})?)\b"
)
NUMBER_WORDS = {
    "primero": 1,
    "primer": 1,
    "primera": 1,
    "segundo": 2,
    "segunda": 2,
    "tercero": 3,
    "tercer": 3,
    "tercera": 3,
    "cuarto": 4,
    "cuarta": 4,
}


class RulesInterpreter:
    name = "rules"

    def interpret(self, masked_text: str, context: dict[str, str]) -> Interpretation:
        text = _fold(masked_text)
        language = Language.PT if _any(PORTUGUESE, text) else Language(context.get("language", "es"))
        human = _any(HUMAN, text)
        claim, confident = self._claim(text, human)
        amount, currency = _amount(text)
        return Interpretation(
            claim_type=claim,
            amount=amount,
            currency=currency,
            date_text=_first_match(DATE_PATTERN, text),
            merchant_text=_merchant(masked_text),
            declared_channel=_channel(text),
            has_card=Answer.NO if _any(NO_CARD, text) else Answer.YES if _any(HAS_CARD, text) else Answer.NOT_SAID,
            authorized_payment=Answer.YES if _any(SCAM, text) else Answer.NOT_SAID,
            coercion=_any(COERCION, text),
            regulator_mentioned=_any(REGULATOR, text),
            pix_mentioned=_any(PIX, text),
            answer=Answer.YES if _any(YES, text) else Answer.NO if _any(NO, text) else Answer.NOT_SAID,
            selected_numbers=_numbers(text, context),
            language=language,
            confidence=0.95 if human or _any(COERCION, text) else 0.85 if confident else 0.4,
        )

    @staticmethod
    def _claim(text: str, human: bool) -> tuple[ClaimType, bool]:
        if human:
            return ClaimType.HUMAN_REQUEST, True
        for claim, patterns in (
            (ClaimType.SCAM_TRANSFER, SCAM),
            (ClaimType.IMPROPER_CHARGE, IMPROPER),
            (ClaimType.UNRECOGNIZED_CHARGE, UNRECOGNIZED),
            (ClaimType.OUT_OF_SCOPE, OUT_OF_SCOPE + PIX),
        ):
            if _any(patterns, text):
                return claim, True
        return ClaimType.UNRECOGNIZED_CHARGE, False


def _first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(0) if match else None


def _channel(text: str) -> DeclaredChannel | None:
    if _any(ONLINE, text):
        return DeclaredChannel.ONLINE
    if _any(IN_PERSON, text):
        return DeclaredChannel.IN_PERSON
    if re.search(r"\b(no se|no recuerdo|nao sei)\b", text):
        return DeclaredChannel.UNKNOWN
    return None


def _amount(text: str) -> tuple[Decimal | None, Currency | None]:
    """First amount in the text: 120.000, 120,000, 45,50 or 87.5, with an optional currency word."""
    pattern = (
        r"(?<![\w/])(\$|us\$|usd |cop |ars |r\$)?\s?(\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,](\d{1,2}))?(?![\d/])\s*([a-z$]+)?"
    )
    for match in re.finditer(pattern, text):
        symbol, whole, cents, word = match.group(1), re.sub(r"[.,]", "", match.group(2)), match.group(3), match.group(4)
        money_word = word in CURRENCY_WORDS or word in ("pesos", "reais")
        # A bare one- or two-digit number is a day, an option or a count, not an amount.
        if not (symbol or money_word or len(whole) >= 3):
            continue
        amount = Decimal(f"{whole}.{cents}") if cents else Decimal(whole)
        return amount, CURRENCY_WORDS.get(word or "") or CURRENCY_WORDS.get((symbol or "").strip())
    return None, None


def _merchant(original: str) -> str | None:
    """Capitalized name after 'de', 'en' or 'em', as in 'un cargo de Uber' or 'compra em Mercado Livre'."""
    match = re.search(r"\b(?:de|en|em|da|do|na|no)\s+((?:[A-ZÁÉÍÓÚÑ][\w&'-]*\s?){1,3})", original)
    if not match:
        return None
    name = match.group(1).strip()
    return None if name.split()[0] in EMPTY_NOUNS else name


def _numbers(text: str, context: dict[str, str]) -> tuple[int, ...]:
    if context.get("expecting") != "choice":
        return ()
    digits = [int(n) for n in re.findall(r"\b([1-9]|[1-4][0-9])\b", text)]
    words = [n for word, n in NUMBER_WORDS.items() if re.search(rf"\b{word}\b", text)]
    return tuple(dict.fromkeys(digits + words))
