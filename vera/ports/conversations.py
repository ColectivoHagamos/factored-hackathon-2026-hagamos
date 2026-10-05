"""Port of the conversations' owners: each conversation belongs to the customer who opened it."""

from typing import Protocol


class ConversationOwnersPort(Protocol):
    def open_conversation(self, conversation_id: str, customer_ref: str) -> None: ...

    def conversation_owner(self, conversation_id: str) -> str | None:
        """The customer who opened the conversation, or None when there is no such conversation."""
        ...
