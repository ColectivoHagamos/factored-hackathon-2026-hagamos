from fastapi import APIRouter, Depends, Request

from api.context import AppContext, get_context
from api.routers import API_PREFIX
from api.schemas import LoginRequest, LoginResponse

router = APIRouter(prefix=API_PREFIX, tags=["access"])


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, context: AppContext = Depends(get_context)) -> LoginResponse:
    return context.access.login(body, request.client.host if request.client else "unknown")
