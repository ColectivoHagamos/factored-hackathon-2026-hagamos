"""Rules interpreter: keyword patterns in Spanish and Portuguese.

It is the baseline the challenge asks for and the fallback when the language model is unavailable. It returns the
same closed schema as any model adapter, and a low confidence when nothing matches, so the flow asks instead of acting.
"""

import re
import unicodedata
from decimal import Decimal

from vera.contracts.common import Currency, Language
from vera.contracts.interpretation import Answer, ClaimType, ContactChannel, DeclaredChannel, Interpretation


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
    r"\bduas\b",
    r"\bvezes\b",
    r"\bpela\b",
    r"\bfalar com\b",
    r"\bpessoa\b",
    r"\bum\b",
    r"\buma\b",
    r"\bnunca fiz\b",
    r"\b(quero|minhas|meus|voces|faturas?|endereco|tambem|ajuda|pode|posso|poupanca|emprestimo|gostaria|aplicativo)\b",
)
HUMAN = (
    r"\b(una persona|un humano|humano|un asesor|asesor|agente humano|alguien real|operador|una persona real)\b",
    r"\b(hablar con alguien|(pase|pasa|pasas|comunique|comunica|comunicas)(me|nos)? con alguien|un agente|"
    r"supervisor|ejecutivo|funcionario|representante|atencion al cliente|servicio al cliente|carne y hueso)\b",
    r"\b(uma pessoa|atendente|falar com alguem|pessoa de verdade|um agente|gerente|supervisor|"
    r"atendimento humano|carne e osso|(passe|passa) (para|pra) alguem)\b",
)
# In a scam story a role is part of the story ("un supuesto asesor del banco me llamó"); it is a request only when
# the customer asks for one in so many words. Reading a request as a story costs nothing: a scam goes to a person.
REQUEST_WORDS = (
    r"\b(quiero|quisiera|necesito|prefiero|hablar con|pase(me|nos)?|pasa(me|nos)?|comunique(me|nos)?|comunica(me|nos)?|"
    r"me atienda|quero|preciso|prefiro|falar com|me passe|me passa|me transfira)\b",
)
# "¿Eres una persona?", "¿es usted un robot?", "você é uma pessoa?": whether VERA is human, asked, not requested.
ASKS_IF_HUMAN = (
    r"\b(eres|es usted|sos|estoy hablando con|hablo con) "
    r"(una persona|un humano|humano|humana|real|un robot|una maquina|un bot|una ia|una inteligencia artificial)\b",
    r"\b(voce e|e voce|estou falando com|falo com) (uma pessoa|um humano|humano|humana|real|um robo|uma maquina|um bot|"
    r"uma ia)\b",
)
COERCION = (
    r"\b(me (estan )?amenaz|amenazad|me obligan|me obligaron|me estan obligando|me (estan )?forz|me forzaron)",
    r"\b(secuestr|extorsi|me tienen retenid|me apuntan)",
    r"\b(ameaca|me obrigam|me obrigaram|me obrigando|me forcaram|sequestr|extorsao)",
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
# A purchase charged more than once (folded text: no accents, lower case).
DUPLICATE = (
    r"\b(dos veces|doble cobro|cobro doble|me cobraron doble|cobrado doble|me la cobraron de nuevo)",
    r"\b(cobro duplicado|cargo duplicado|compra duplicada|cargo repetido|cobro repetido|compra repetida)",
    r"\b(duas vezes|em dobro|cobranca duplicada|cobranca repetida|compra duplicada)",
)
IMPROPER = (
    *DUPLICATE,
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
# A lost or stolen card opens a dispute even before a charge is named: VERA protects the card first.
LOST_CARD = (
    r"\b(me robaron (la|mi) tarjeta|me la robaron|robaron mi tarjeta|perdi (la|mi) tarjeta|"
    r"se me perdio (la|mi) tarjeta|me clonaron (la|mi) tarjeta|extravie (la|mi) tarjeta)",
    r"\b(roubaram (o |meu )?cartao|perdi (o |meu )?cartao|furtaram (o |meu )?cartao|clonaram (o |meu )?cartao)",
)
# Worry, fear, anger or frustration: VERA validates the emotion before the next step, and never argues with it.
DISTRESS = (
    r"\b(preocupad[oa]|asustad[oa]|desesperad[oa]|angustiad[oa]|nervios[oa]|estresad[oa]|indignad[oa]|furios[oa])",
    r"\b(tengo miedo|me da miedo|que susto|estoy (muy )?mal|no se que hacer|no puede ser|es un abuso|es una verguenza|"
    r"estoy hart[oa]|me siento (impotente|mal))",
    r"\b(assustad[oa]|com medo|desesperad[oa]|nervos[oa]|irritad[oa]|que absurdo|nao sei o que fazer|estou mal)",
)
# Greetings, thanks, small talk and pleas for help: they say nothing of the claim yet, so VERA welcomes and orients.
GREETING = (
    r"^\s*(hola|holi|buenas|buen dia|buenos dias|buenas tardes|buenas noches|hey|ola|oi|bom dia|boa tarde|boa noite)\b",
    r"\b(necesito (tu |su )?ayuda|ayudame|ayudeme|me ayudas|me puedes ayudar|me puede ayudar|preciso de ajuda|"
    r"pode me ajudar|me ajuda|me ajude)\b",
    r"\b(como estas|como esta|que tal|tudo bem|como vai)\b",
    r"\b(que es esto|quien eres|quien es usted|que haces|para que sirves|o que e isso|quem e voce)\b",
    r"^\s*(gracias|muchas gracias|obrigad[oa])\b",
)
YES = (r"^\s*(si|sim|claro|correcto|ok|dale|de acuerdo|confirmo|exacto|afirmativo|isso)\b",)
NO = (r"^\s*(no|nao|nunca|negativo|para nada)\b",)
EMPTY_NOUNS = {"El", "La", "Los", "Las", "Un", "Una", "Mi", "Me", "Que", "Hola", "Buenas", "Ayer", "Hoy", "O", "A"}
# Capitalized words that never name a merchant: months, days and the words a sentence often starts with.
NOT_MERCHANTS = EMPTY_NOUNS | {
    *("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre"),
    *("Noviembre", "Diciembre", "Janeiro", "Fevereiro", "Março", "Maio", "Junho", "Julho", "Setembro", "Outubro"),
    *("Novembro", "Dezembro", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"),
    *("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sí", "Sim", "No", "Não", "Gracias", "Obrigado"),
    *("Obrigada", "Oi", "Olá", "Por", "Para", "Pero", "Mas"),
}
CAPITALIZED = re.compile(r"[A-ZÁÉÍÓÚÑ][\w&'-]*")
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
# POL-10: how a third party reached the customer, checked in this order: a call over WhatsApp is still a call.
# "Me llamó" is left out: without accents it is "me llamo", which introduces a name.
CONTACT = (
    (ContactChannel.PHONE_CALL, r"\b(me llamaron|llamada|llamaron|telefono|telefone|celular|ligaram|ligacao|ligou)\b"),
    (ContactChannel.MESSAGE, r"\b(whatsapp|wsp|wpp|zap|telegram|sms|mensaje de texto|mensajito|mensagem|mensajes?)\b"),
    (ContactChannel.EMAIL, r"\b(correo|e-?mail|mail)\b"),
    (ContactChannel.SOCIAL_MEDIA, r"\b(facebook|instagram|tiktok|redes sociales|marketplace|twitter|redes)\b"),
    (ContactChannel.WEBSITE, r"\b(pagina|sitio web|enlace|link|site)\b"),
    (ContactChannel.IN_PERSON, r"\b(en persona|presencial|en la calle|pessoalmente)\b"),
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
        asks_if_human = _any(ASKS_IF_HUMAN, text)
        # The question names a person without asking for one; a request in the same message still counts.
        rest = re.sub("|".join(ASKS_IF_HUMAN), " ", text)
        human = _any(HUMAN, rest) and not (_any(SCAM, rest) and not _any(REQUEST_WORDS, rest))
        claim, confident = self._claim(rest, human)
        amount, currency = _amount(text)
        return Interpretation(
            claim_type=claim,
            amount=amount,
            currency=currency,
            date_text=_first_match(DATE_PATTERN, text),
            merchant_text=_merchant(masked_text),
            declared_channel=_channel(text),
            has_card=Answer.NO
            if _any(NO_CARD + LOST_CARD, text)
            else Answer.YES
            if _any(HAS_CARD, text)
            else Answer.NOT_SAID,
            authorized_payment=Answer.YES if _any(SCAM, text) else Answer.NOT_SAID,
            contact_channel=next((channel for channel, pattern in CONTACT if re.search(pattern, text)), None),
            coercion=_any(COERCION, text),
            regulator_mentioned=_any(REGULATOR, text),
            pix_mentioned=_any(PIX, text),
            asks_if_human=asks_if_human,
            greeting=_only_greeting(text) and not confident and amount is None,
            distress=_any(DISTRESS, text),
            duplicate=_any(DUPLICATE, text),
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
            (ClaimType.UNRECOGNIZED_CHARGE, UNRECOGNIZED + LOST_CARD),
            (ClaimType.OUT_OF_SCOPE, OUT_OF_SCOPE + PIX),
        ):
            if _any(patterns, text):
                return claim, True
        return ClaimType.UNRECOGNIZED_CHARGE, False


def _only_greeting(text: str) -> bool:
    """A greeting, thanks, small talk or a plea for help with little else; a message that says more is a claim."""
    if not _any(GREETING, text):
        return False
    rest = re.sub("|".join(GREETING), " ", text)
    return len(re.findall(r"[a-z]{3,}", rest)) <= 3


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
    """The merchant or place the customer named.

    First a capitalized name after a preposition ("un cargo de Uber", "compra em Mercado Livre"); else one anywhere
    else ("aparece Hotel Prado en mis movimientos"), so a name is not lost because of how the sentence was built.
    """
    for match in re.finditer(r"\b(?:de|en|em|da|do|na|no)\s+((?:[A-ZÁÉÍÓÚÑ][\w&'-]*\s?){1,3})", original):
        name = match.group(1).strip()
        if name.split()[0] not in NOT_MERCHANTS:
            return name
    words = [word.group() for word in re.finditer(r"\S+", original)]
    index = 0
    while index < len(words):
        name = _capitalized_run(words, index)
        starts_sentence = index == 0 or words[index - 1][-1] in ".!?:¿¡"
        # A capital at the start of a sentence is grammar, unless two or more names follow each other.
        if name and (not starts_sentence or len(name) > 1):
            return " ".join(name)
        index += max(1, len(name))
    return None


def _capitalized_run(words: list[str], start: int) -> list[str]:
    """Up to three capitalized words from start that are not common words, as in "Hotel Prado"."""
    run = []
    for word in words[start : start + 3]:
        text = word.strip(',;:()¿?¡!"')
        if not CAPITALIZED.fullmatch(text) or text in NOT_MERCHANTS:
            break
        run.append(text)
        if word[-1] in ",;:.!?":
            break
    return run


def _numbers(text: str, context: dict[str, str]) -> tuple[int, ...]:
    if context.get("expecting") != "choice":
        return ()
    digits = [int(n) for n in re.findall(r"\b([1-9]|[1-4][0-9])\b", text)]
    words = [n for word, n in NUMBER_WORDS.items() if re.search(rf"\b{word}\b", text)]
    return tuple(dict.fromkeys(digits + words))
