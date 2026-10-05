from fastapi import APIRouter, Depends, Request

from api.context import AppContext, get_context
from api.guards import customer_session
from api.routers import API_PREFIX
from api.schemas import StartConversationRequest, StartConversationResponse
from api.security import SessionToken
from vera.contracts.conversation import MessageRequest, MessageResponse

router = APIRouter(prefix=API_PREFIX, tags=["conversation"])


@router.post("/conversations", response_model=StartConversationResponse)
def start(
    body: StartConversationRequest,
    session: SessionToken = Depends(customer_session),
    context: AppContext = Depends(get_context),
) -> StartConversationResponse:
    return context.conversations.start(session.subject, body.preferred_language)


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
def message(
    conversation_id: str,
    body: MessageRequest,
    request: Request,
    session: SessionToken = Depends(customer_session),
    context: AppContext = Depends(get_context),
) -> MessageResponse:
    return context.conversations.reply(session.subject, conversation_id, body, request.state.request_id)
