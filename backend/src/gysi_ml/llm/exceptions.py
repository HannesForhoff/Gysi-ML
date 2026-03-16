class LLMConnectionError(Exception):
    """Fehler bei der Kommunikation mit dem LLM-Endpunkt."""


class LLMResponseValidationError(Exception):
    """LLM-Antwort erfüllt das erwartete JSON-Schema nicht."""
