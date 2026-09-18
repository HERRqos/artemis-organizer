"""Tool registry: schemas the LLM sees + the dispatch that runs them.

Adding a tool means one schema and one handler. conversation.py never
learns their names.
"""
from datetime import datetime, timedelta
from typing import Any, Callable

from assistant_shared.config import Settings

from assistant_shared.calendar import CalendarService
from .practice import PracticeInfo

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "check_availability",
        "description": (
            "Devuelve horarios libres reales de la consulta. Úsala siempre antes "
            "de ofrecer una hora. Nunca inventes disponibilidad."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "Fecha inicio, YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "Fecha fin, YYYY-MM-DD"},
            },
            "required": ["date_from", "date_to"],
        },
    },
    {
        "name": "book_appointment",
        "description": "Reserva una cita en un horario que check_availability devolvió como libre.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Inicio ISO 8601, p.ej. 2026-09-15T10:00:00"},
                "client_name": {"type": "string"},
                "note": {"type": "string", "description": "Nota breve y no clínica, opcional"},
            },
            "required": ["start", "client_name"],
        },
    },
    {
        "name": "reschedule_appointment",
        "description": "Mueve la próxima cita de este contacto a un horario libre.",
        "input_schema": {
            "type": "object",
            "properties": {"new_start": {"type": "string"}},
            "required": ["new_start"],
        },
    },
    {
        "name": "cancel_appointment",
        "description": "Cancela la próxima cita de este contacto.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_practice_info",
        "description": (
            "Consulta la información propia de la consulta (horarios, precios, "
            "ubicación, primera sesión). Úsala en vez de responder de memoria."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Deriva la conversación a la psicóloga. Úsala para cualquier contenido "
            "clínico, emocional, urgencias o quejas. Tras llamarla, no respondas más."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
]


class ToolContext:
    def __init__(self, settings: Settings, calendar: CalendarService,
                 practice: PracticeInfo, sender: str):
        self.settings = settings
        self.calendar = calendar
        self.practice = practice
        self.sender = sender
        self.escalated = False
        self.escalation_reason = ""
        self.booking_summary:str|None=None


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def _parse(value: str, ctx: ToolContext) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=ctx.settings.tz)


def _check_availability(args: dict, ctx: ToolContext) -> dict:
    start = _parse(args["date_from"] + "T00:00:00", ctx)
    end = _parse(args["date_to"] + "T23:59:59", ctx)
    slots = ctx.calendar.free_slots(start, end)[:12]
    return {"slots": [_fmt(s) for s in slots]}


def _book(args: dict, ctx: ToolContext) -> dict:
    start = _parse(args["start"], ctx)
    end= start + timedelta(minutes=ctx.settings.slot_minutes)
    if start not in ctx.calendar.free_slots(start, end):
        return {"ok": False, "error": "slot_taken"}
    appt = ctx.calendar.book(start, ctx.sender, args["client_name"], args.get("note", ""))
    ctx.booking_summary=f"Nueva cita: {args['client_name']} - {_fmt(appt.start)}"
    return {"ok": True, "start": _fmt(appt.start),"add_to_calendar_url":appt.add_to_calendar_url}


def _reschedule(args: dict, ctx: ToolContext) -> dict:
    existing = ctx.calendar.appointment_for(ctx.sender)
    if not existing:
        return {"ok": False, "error": "no_appointment_found"}
    new_start = _parse(args["new_start"], ctx)
    new_end= new_start+timedelta(minutes=ctx.settings.slot_minutes)
    if new_start not in ctx.calendar.free_slots(new_start, new_end):
        return {"ok": False, "error": "slot_taken"}
    appt = ctx.calendar.move(existing.event_id, new_start)
    ctx.booking_summary=f"Cita reprogramada:{ctx.sender} - {_fmt(appt.start)}"
    return {"ok": True, "start": _fmt(appt.start)}


def _cancel(_args: dict, ctx: ToolContext) -> dict:
    existing = ctx.calendar.appointment_for(ctx.sender)
    if not existing:
        return {"ok": False, "error": "no_appointment_found"}
    ctx.calendar.cancel(existing.event_id)
    ctx.booking_summary=f"Cita cancelada:{ctx.sender} - {_fmt(existing.start)}"
    return {"ok": True, "cancelled": _fmt(existing.start)}


def _practice_info(args: dict, ctx: ToolContext) -> dict:
    hits = ctx.practice.search(args["question"])
    return {"answers": [h.answer for h in hits]} if hits else {"answers": [], "note": "sin_datos"}


def _escalate(args: dict, ctx: ToolContext) -> dict:
    ctx.escalated = True
    ctx.escalation_reason = args.get("reason", "")
    return {"ok": True}


HANDLERS: dict[str, Callable[[dict, ToolContext], dict]] = {
    "check_availability": _check_availability,
    "book_appointment": _book,
    "reschedule_appointment": _reschedule,
    "cancel_appointment": _cancel,
    "get_practice_info": _practice_info,
    "escalate_to_human": _escalate,
}


def dispatch(name: str, args: dict, ctx: ToolContext) -> dict:
    handler = HANDLERS.get(name)
    if handler is None:
        return {"ok": False, "error": f"unknown_tool:{name}"}
    try:
        return handler(args, ctx)
    except Exception as exc:  # tool errors go back to the model, not the user
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}
