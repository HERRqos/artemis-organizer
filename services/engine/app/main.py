"""Conversation engine worker: consume queue -> think -> reply."""
import logging
import os
import socket

from assistant_shared.config import load_settings
from assistant_shared.models import InboundMessage
from assistant_shared.queue import RedisStreamQueue
from assistant_shared.whatsapp import WhatsAppClient

from .conversation import Conversation
from .escalation import needs_immediate_handoff
from .llm import AnthropicLLM
from .prompts import HANDOFF_MESSAGE
from .session import SessionStore
from .tools import ToolContext
from assistant_shared.calendar import CalendarService
from .tools.practice import PracticeInfo

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("engine")

OWNER_NAME = os.environ.get("OWNER_NAME", "la psicóloga")


def main() -> None:
    settings = load_settings()
    queue = RedisStreamQueue(settings.redis_url, settings.queue_name)
    sessions = SessionStore(settings.redis_url)
    whatsapp = WhatsAppClient(settings)
    calendar = CalendarService(settings)
    practice = PracticeInfo()
    conversation = Conversation(
        settings, AnthropicLLM(settings.anthropic_api_key, settings.llm_model), OWNER_NAME
    )
    consumer = f"engine-{socket.gethostname()}"
    log.info("worker %s listening on %s", consumer, settings.queue_name)

    while True:
        for item in queue.consume(consumer, count=1, block_ms=5000):
            try:
                handle(
                    InboundMessage.from_dict(item.payload),
                    settings, sessions, whatsapp, calendar, practice, conversation,
                )
            except Exception:
                log.exception("failed to handle %s", item.payload.get("message_id"))
            finally:
                # ack regardless: a poisoned message must not loop forever.
                queue.ack(item.receipt)

def notify_owner_booking(whatsapp,settings,msg,summary:str)->None:
    if not settings.owner_whatsapp:
        return
    whatsapp.send_text(
        settings.owner_whatsapp,
        f"{summary}\nDe: {msg.profile_name or msg.sender} ({msg.sender})",
    )

def handle(msg, settings, sessions, whatsapp, calendar, practice, conversation) -> None:
    if sessions.is_escalated(msg.sender):
        log.info("sender %s is in human handoff, staying quiet", msg.sender)
        return

    if needs_immediate_handoff(msg.text):
        notify_owner(whatsapp, settings, msg, "keyword gate")
        sessions.escalate(msg.sender)
        whatsapp.send_text(msg.sender, HANDOFF_MESSAGE.format(owner=OWNER_NAME))
        return

    ctx = ToolContext(settings, calendar, practice, msg.sender)
    reply, history = conversation.run(msg.text, sessions.history(msg.sender), ctx)
    sessions.save(msg.sender, history)

    if ctx.escalated:
        notify_owner(whatsapp, settings, msg, ctx.escalation_reason)
        sessions.escalate(msg.sender)
    elif ctx.booking_summary:
        notify_owner_booking(whatsapp,settings,msg,ctx.booking_summary)

    if reply:
        whatsapp.send_text(msg.sender, reply)


def notify_owner(whatsapp, settings, msg, reason: str) -> None:
    if not settings.owner_whatsapp:
        return
    whatsapp.send_text(
        settings.owner_whatsapp,
        f"Handoff ({reason})\nDe: {msg.profile_name or msg.sender} ({msg.sender})\n\n{msg.text}",
    )


if __name__ == "__main__":
    main()
