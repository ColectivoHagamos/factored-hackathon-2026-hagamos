"""Invented names for the demo customers, so a reviewer talks to someone; the dataset subset holds no names (P09).

The names are fictional and common in each country, assigned by the customer's place among those of its country, so
they stay the same across restarts. Customers of the Portuguese scenario (A6) alone get Brazilian names and
Portuguese; the client still chooses the language of each conversation.
"""

from dataclasses import dataclass

from vera.contracts.common import Country, Language
from vera.ports.bank import CustomerRecord

FIRST = {
    Country.CO: ("Ana", "Camilo", "Laura", "Andrés", "Valentina", "Santiago", "Daniela", "Felipe", "Mariana", "Julián"),
    Country.MX: ("Sofía", "Diego", "Fernanda", "Emiliano", "Regina", "Mateo", "Ximena", "Leonardo", "Renata", "Iván"),
    Country.AR: (
        "Martina",
        "Tomás",
        "Lucía",
        "Joaquín",
        "Catalina",
        "Facundo",
        "Agustina",
        "Nicolás",
        "Julieta",
        "Bruno",
    ),
}
LAST = {
    Country.CO: ("Gómez", "Rodríguez", "Martínez", "Castro", "Ramírez", "Moreno", "Rojas", "Vargas", "Ortiz", "Silva"),
    Country.MX: ("Hernández", "García", "López", "Flores", "Sánchez", "Torres", "Ruiz", "Mendoza", "Cruz", "Navarro"),
    Country.AR: (
        "Fernández",
        "González",
        "Pérez",
        "Romero",
        "Sosa",
        "Álvarez",
        "Benítez",
        "Acosta",
        "Medina",
        "Herrera",
    ),
}
PORTUGUESE_FIRST = ("Lucas", "Beatriz", "Gabriel", "Larissa", "Rafael", "Camila", "Thiago", "Juliana", "Bruno", "Paula")
PORTUGUESE_LAST = (
    "Pereira",
    "Souza",
    "Oliveira",
    "Carvalho",
    "Ribeiro",
    "Almeida",
    "Costa",
    "Barbosa",
    "Lima",
    "Rocha",
)


@dataclass(frozen=True)
class Persona:
    display_name: str
    first_name: str
    language: Language


def personas(customers: tuple[CustomerRecord, ...]) -> dict[str, Persona]:
    """One stable, invented name per customer reference; first and last names never repeat as a pair."""
    found: dict[str, Persona] = {}
    places: dict[object, int] = {}
    for customer in sorted(customers, key=lambda c: c.alias):
        tags = [tag.split("_")[0] for tag in customer.scenarios]
        # Only a customer chosen for the Portuguese scenario alone speaks Portuguese; one that serves several does not.
        portuguese = bool(tags) and all(tag == "A6" for tag in tags)
        group = "pt" if portuguese else customer.country
        index = places.get(group, 0)
        places[group] = index + 1
        if portuguese:
            firsts, lasts = PORTUGUESE_FIRST, PORTUGUESE_LAST
        else:
            firsts, lasts = FIRST[customer.country], LAST[customer.country]
        first = firsts[index % len(firsts)]
        last = lasts[(3 * index + index // len(firsts)) % len(lasts)]
        found[customer.customer_ref] = Persona(f"{first} {last}", first, Language.PT if portuguese else Language.ES)
    return found
