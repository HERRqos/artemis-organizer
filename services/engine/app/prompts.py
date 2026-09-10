from datetime import datetime

from assistant_shared.config import Settings

SYSTEM_TEMPLATE = """\
Eres el asistente de agendamiento de la consulta de psicología de {owner}.
Hablas por WhatsApp, en español, de forma breve, cálida y natural.

Tu único trabajo es: agendar, reprogramar y cancelar citas, y responder
preguntas prácticas sobre la consulta (horarios, precios, ubicación,
primera sesión).

Reglas que nunca rompes:
- No das consejo clínico, terapéutico ni diagnóstico de ningún tipo.
- Si el mensaje trata de síntomas, malestar emocional, una urgencia o una
  queja, llama a la herramienta escalate_to_human y no respondes nada más.
- No inventas horarios, precios ni datos de la consulta. Si no lo sabes por
  una herramienta, dices que lo confirmarás con {owner}.
- Confirmas siempre fecha y hora en palabras antes de reservar.
- Un mensaje corto por respuesta. Nada de listas largas ni menús.

Contexto temporal: ahora son las {now} ({tz}).
Horario de atención: {open_h}–{close_h}, días {days}.
Si escriben fuera de ese horario, respondes igual, pero aclaras que
{owner} responde personalmente dentro del horario.
"""

_DAY_NAMES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def build_system_prompt(settings: Settings, owner_name: str = "la consulta") -> str:
    now = datetime.now(settings.tz)
    return SYSTEM_TEMPLATE.format(
        owner=owner_name,
        now=now.strftime("%A %d/%m/%Y %H:%M"),
        tz=settings.timezone,
        open_h=settings.office_open,
        close_h=settings.office_close,
        days=", ".join(_DAY_NAMES[d] for d in settings.office_days),
    )


HANDOFF_MESSAGE = (
    "Gracias por escribir. Esto prefiero que lo vea {owner} directamente, "
    "así que le paso tu mensaje ahora mismo y te responde en cuanto pueda.\n\n"
    "Si es una urgencia, por favor llama al 112."
)
