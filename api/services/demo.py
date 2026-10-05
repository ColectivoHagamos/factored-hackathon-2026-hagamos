"""The demo's directory: the customers with their invented names, and the sessions the demo opens for them."""

import hmac

from api.dependencies import Container
from api.failures import ApiFailure
from api.personas import Persona, personas
from api.schemas import ApiErrorCode, DemoCustomer, DemoSessionResponse
from api.security import IssuedToken


class DemoDirectory:
    def __init__(self, container: Container, analyst_key: str) -> None:
        self._container = container
        # Empty: the demo analyst view is open, on purpose; set: the analyst session requires it.
        self._analyst_key = analyst_key
        self._people: dict[str, Persona] = {}

    def people(self) -> dict[str, Persona]:
        """The invented name of each demo customer, computed once, on first use."""
        if not self._people:
            self._people.update(personas(self._container.customers.customers()))
        return self._people

    def persona(self, customer_ref: str) -> Persona | None:
        return self.people().get(customer_ref)

    def customers(self) -> list[DemoCustomer]:
        people = self.people()
        return [
            DemoCustomer(
                customer_ref=customer.customer_ref,
                display_name=people[customer.customer_ref].display_name,
                first_name=people[customer.customer_ref].first_name,
                alias=customer.alias,
                country=customer.country.value,
                segment=customer.segment,
                scenarios=list(customer.scenarios),
                language=people[customer.customer_ref].language.value,
            )
            for customer in self._container.customers.customers()
        ]

    def customer_session(self, customer_ref: str) -> DemoSessionResponse:
        if self._container.customers.customer(customer_ref) is None:
            raise ApiFailure(ApiErrorCode.NOT_FOUND)
        return _session(self._container.signer.issue(customer_ref))

    def analyst_session(self, key: str) -> DemoSessionResponse:
        if self._analyst_key and not hmac.compare_digest(key, self._analyst_key):
            raise ApiFailure(ApiErrorCode.UNAUTHORIZED)
        return _session(self._container.signer.issue("demo-analyst", role="analyst"))


def _session(issued: IssuedToken) -> DemoSessionResponse:
    return DemoSessionResponse(token=issued.token, expires_at=issued.expires_at)
