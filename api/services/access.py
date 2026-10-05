"""The login to the demo: an account checked against its salted hash, a limit per address, a JSON Web Token."""

from api.access import Accounts
from api.failures import ApiFailure
from api.limits import RateLimiter
from api.schemas import ApiErrorCode, LoginRequest, LoginResponse
from api.security import ACCESS_TTL, SessionSigner


class AccessService:
    def __init__(self, accounts: Accounts, signer: SessionSigner, logins: RateLimiter) -> None:
        self._accounts = accounts
        self._signer = signer
        self._logins = logins

    @property
    def open(self) -> bool:
        """No account is configured: the demo needs no login, as in development and the CI."""
        return self._accounts.open

    def login(self, body: LoginRequest, address: str) -> LoginResponse:
        self._logins.check(address)
        if not self._accounts.open and not self._accounts.check(body.username, body.password):
            raise ApiFailure(ApiErrorCode.UNAUTHORIZED)
        issued = self._signer.issue(body.username, role="tester", ttl=ACCESS_TTL)
        return LoginResponse(
            token=issued.token, expires_at=issued.expires_at, display_name=body.username, role="tester"
        )
