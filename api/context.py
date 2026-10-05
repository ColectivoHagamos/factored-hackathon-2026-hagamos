"""Everything a request needs, built once per application: the settings, the container, the metrics and the use
cases. Routers reach it through FastAPI's dependency injection, never through module globals."""

from dataclasses import dataclass

from fastapi import Request

from api.access import Accounts
from api.dependencies import Container
from api.limits import RateLimiter
from api.observability import Metrics
from api.services.access import AccessService
from api.services.analyst import AnalystDesk
from api.services.conversations import ConversationService
from api.services.customer import CustomerViews
from api.services.data import DataOverviewService
from api.services.demo import DemoDirectory
from api.settings import Settings

LOGINS_PER_MINUTE = 10


@dataclass(frozen=True)
class AppContext:
    settings: Settings
    container: Container
    metrics: Metrics
    access: AccessService
    demo: DemoDirectory
    customers: CustomerViews
    conversations: ConversationService
    analyst: AnalystDesk
    data: DataOverviewService


def build_context(settings: Settings, container: Container) -> AppContext:
    """The use cases, each given the ports and the core it needs; none of them sees the container."""
    metrics = Metrics()
    demo = DemoDirectory(container.customers, container.signer, settings.analyst_key)
    logins = RateLimiter(LOGINS_PER_MINUTE, container.now)
    messages = RateLimiter(settings.messages_per_minute, container.now)
    customers = CustomerViews(
        customers=container.customers,
        cards=container.cards,
        transactions=container.transactions,
        tools=container.tools,
        handoffs=container.state,
        now=container.now,
        demo=demo,
    )
    return AppContext(
        settings=settings,
        container=container,
        metrics=metrics,
        access=AccessService(Accounts(settings.testers), container.signer, logins),
        demo=demo,
        customers=customers,
        conversations=ConversationService(container.conversation, container.state, demo, metrics, messages),
        analyst=AnalystDesk(container.state),
        data=DataOverviewService(
            customers=container.customers,
            cards=container.cards,
            transactions=container.transactions,
            now=container.now,
        ),
    )


def get_context(request: Request) -> AppContext:
    return request.app.state.context
