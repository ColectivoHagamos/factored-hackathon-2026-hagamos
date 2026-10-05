"""Who is calling. Each guard turns the bearer token into a session of one role or answers 401; the access guard lets
everyone in when no account is configured, as in development and the CI."""

from fastapi import Depends, Header

from api.context import AppContext, get_context
from api.failures import ApiFailure
from api.schemas import ApiErrorCode
from api.security import InvalidSessionError, SessionToken


def customer_session(
    authorization: str = Header(default=""), context: AppContext = Depends(get_context)
) -> SessionToken:
    return _verify(context, authorization, "customer")


def analyst_session(
    authorization: str = Header(default=""), context: AppContext = Depends(get_context)
) -> SessionToken:
    return _verify(context, authorization, "analyst")


def access_session(
    authorization: str = Header(default=""), context: AppContext = Depends(get_context)
) -> SessionToken | None:
    """The login to the demo, when accounts are configured; without them the demo stays open."""
    if context.access.open:
        return None
    return _verify(context, authorization, "tester")


def _verify(context: AppContext, authorization: str, role: str) -> SessionToken:
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return context.container.signer.verify(token, role)
    except InvalidSessionError as error:
        raise ApiFailure(ApiErrorCode.UNAUTHORIZED) from error
