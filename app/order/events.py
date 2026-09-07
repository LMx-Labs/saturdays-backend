import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.order.websocket_manager import ws_manager


class OrderEventPublisher:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def publish(
        self, branch_id: uuid.UUID, event: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        envelope = {
            "event_id": str(uuid.uuid4()),
            "event": event,
            "branch_id": str(branch_id),
            "occurred_at": datetime.now(UTC).isoformat(),
            "resync_cursor": datetime.now(UTC).isoformat(),
            **payload,
        }
        if self.session.bind and self.session.bind.dialect.name == "postgresql":
            await self.session.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {
                    "channel": f"branch_orders_{str(branch_id).replace('-', '_')}",
                    "payload": json.dumps(envelope),
                },
            )
            await self.session.commit()
        await ws_manager.broadcast_to_branch(branch_id, envelope)
        return envelope
