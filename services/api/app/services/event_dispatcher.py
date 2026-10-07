import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.api.app.core.logging import get_logger
from services.api.app.core.redis import get_redis

logger = get_logger("event_dispatcher")

# In-memory event audit log for testing/verification
_in_memory_event_log: List[Dict[str, Any]] = []


def _json_serial(obj: Any) -> Any:
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


class EventDispatcher:
    """Dispatches real-time domain events to Redis Pub/Sub channels and local audit logs."""

    @classmethod
    async def emit(
        cls,
        event_type: str,
        org_id: uuid.UUID,
        payload: Dict[str, Any],
        lead_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        event_record = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "organization_id": str(org_id),
            "lead_id": str(lead_id) if lead_id else None,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Store in local memory log (last 200 events)
        _in_memory_event_log.append(event_record)
        if len(_in_memory_event_log) > 200:
            _in_memory_event_log.pop(0)

        # Dispatch via Redis PubSub
        try:
            client = get_redis()
            msg = json.dumps(event_record, default=_json_serial)
            await client.publish(f"events:{org_id}", msg)
            await client.publish(f"events:{event_type}", msg)
        except Exception as e:
            logger.debug(
                "Redis publish bypassed or unavailable",
                event_type=event_type,
                org_id=str(org_id),
                error=str(e),
            )

        logger.info(
            "Domain event emitted",
            event_type=event_type,
            org_id=str(org_id),
            lead_id=str(lead_id) if lead_id else None,
        )
        return event_record

    @classmethod
    async def dispatch(
        cls,
        event_type: str,
        data: Dict[str, Any],
        organization_id: uuid.UUID,
        lead_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        return await cls.emit(
            event_type=event_type,
            org_id=organization_id,
            payload=data,
            lead_id=lead_id,
        )

    @classmethod
    def get_recent_events(cls, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        if event_type:
            return [e for e in _in_memory_event_log if e["event_type"] == event_type]
        return list(_in_memory_event_log)

    @classmethod
    def clear_events(cls) -> None:
        _in_memory_event_log.clear()

