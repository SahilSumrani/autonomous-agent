import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from services.api.app.core.logging import get_logger
from services.api.app.core.redis import get_redis

logger = get_logger("event_dispatcher")

# In-memory event audit log for testing/verification
_in_memory_event_log: List[Dict[str, Any]] = []
_subscribers: Set[Callable[[Dict[str, Any]], Any]] = set()


def _json_serial(obj: Any) -> Any:
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


class EventDispatcher:
    """
    Dispatches real-time domain notifications via best-effort Redis Pub/Sub channels
    and local in-memory audit logs.
    
    IMPORTANT ARCHITECTURAL TRUTH:
    This is an ephemeral publish/subscribe broadcast mechanism for real-time UI/extension
    notifications and telemetry. It is NOT a durable task queue, persistent message broker,
    or background worker system. If no subscriber is actively listening to a channel,
    published events are immediately dropped by Redis.
    """

    @classmethod
    async def emit(
        cls,
        event_type: str,
        org_id: uuid.UUID,
        payload: Dict[str, Any],
        lead_id: Optional[uuid.UUID] = None,
        job_id: Optional[uuid.UUID] = None,
        session_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        resolved_job_id = str(job_id) if job_id else (str(payload.get("job_id")) if payload.get("job_id") else None)
        resolved_session_id = str(session_id) if session_id else (str(payload.get("session_id")) if payload.get("session_id") else None)
        
        event_record = {
            "event_id": str(uuid.uuid4()),
            "job_id": resolved_job_id,
            "session_id": resolved_session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "organization_id": str(org_id),
            "lead_id": str(lead_id) if lead_id else None,
            "payload": payload,
        }

        # Store in local memory log (last 200 events)
        _in_memory_event_log.append(event_record)
        if len(_in_memory_event_log) > 200:
            _in_memory_event_log.pop(0)

        # Dispatch via Redis PubSub (best-effort broadcast)
        try:
            client = get_redis()
            msg = json.dumps(event_record, default=_json_serial)
            await client.publish(f"events:{org_id}", msg)
            await client.publish(f"events:{event_type}", msg)
        except Exception as e:
            logger.warning(
                "Redis broadcast publish failed; event retained in local audit log",
                event_type=event_type,
                org_id=str(org_id),
                error=str(e),
            )

        # Direct in-process subscriber notifications
        for callback in list(_subscribers):
            try:
                res = callback(event_record)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception as sub_err:
                logger.warning(f"Subscriber callback error: {sub_err}")

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
        job_id: Optional[uuid.UUID] = None,
        session_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        return await cls.emit(
            event_type=event_type,
            org_id=organization_id,
            payload=data,
            lead_id=lead_id,
            job_id=job_id,
            session_id=session_id,
        )

    @classmethod
    def subscribe(cls, callback: Any) -> None:
        _subscribers.add(callback)

    @classmethod
    def unsubscribe(cls, callback: Any) -> None:
        _subscribers.discard(callback)

    @classmethod
    def get_recent_events(cls, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        if event_type:
            return [e for e in _in_memory_event_log if e["event_type"] == event_type]
        return list(_in_memory_event_log)

    @classmethod
    def clear_events(cls) -> None:
        _in_memory_event_log.clear()


