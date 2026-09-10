from services.engine.app.escalation import needs_immediate_handoff


def test_crisis_language_never_reaches_the_model():
    assert needs_immediate_handoff("creo que quiero suicidarme")
    assert needs_immediate_handoff("es una EMERGENCIA")
    assert needs_immediate_handoff("quiero hacerme daño")  # accent-insensitive


def test_ordinary_booking_talk_passes_through():
    assert not needs_immediate_handoff("hola, quiero pedir cita para el jueves")
    assert not needs_immediate_handoff("¿cuánto cuesta la sesión?")
