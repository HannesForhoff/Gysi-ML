from gysi_ml.config import get_settings
from gysi_ml.core.capabilities import get_capabilities
from gysi_ml.executor.executor import PipelineExecutor
from gysi_ml.llm.client import call_llm
from gysi_ml.llm.exceptions import LLMConnectionError, LLMResponseValidationError
from gysi_ml.llm.prompts import build_retry_prompt, build_system_prompt
from gysi_ml.llm.response_schema import validate_llm_response
from gysi_ml.persistence import message_repository

LLM_NOT_CONFIGURED = "llm_not_configured"


def handle_message(
    session_id: str,
    text: str,
    db_path: str | None = None,
    data_path: str | None = None,
    artifacts_path: str | None = None,
) -> dict:
    """Koordiniert den Nachrichtenfluss: Text -> LLM -> Ausführung/Proposal.

    Returns:
        dict mit Pflichtfeld 'type' ('proposal', 'result', 'error')
    """
    settings = get_settings()

    # 1. LLM-Konfiguration prüfen
    if not settings.openai_api_key or not settings.llm_model:
        return {
            "type": "error",
            "error_code": LLM_NOT_CONFIGURED,
            "message": (
                "LLM-Service nicht konfiguriert. "
                "Bitte OPENAI_API_KEY und LLM_MODEL in .env setzen."
            ),
        }

    # 2. Capabilities laden und System-Prompt bauen
    capabilities = get_capabilities()["steps"]
    system_prompt = build_system_prompt(capabilities)

    # 3. Gesprächshistorie laden und messages-Array aufbauen
    history = message_repository.get_messages_for_session(
        session_id=session_id, db_path=db_path
    )
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # 4. LLM aufrufen
    try:
        llm_response_str = call_llm(
            messages=messages,
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )
    except LLMConnectionError as exc:
        return {"type": "error", "message": f"Fehler bei der LLM-Kommunikation: {exc}"}

    # 5. Validierung mit Retry
    try:
        parsed = validate_llm_response(llm_response_str)
    except LLMResponseValidationError as first_error:
        retry_prompt = build_retry_prompt(str(first_error))
        messages.append({"role": "assistant", "content": llm_response_str})
        messages.append({"role": "user", "content": retry_prompt})
        try:
            llm_retry_str = call_llm(
                messages=messages,
                model=settings.llm_model,
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url or None,
            )
            parsed = validate_llm_response(llm_retry_str)
        except (LLMResponseValidationError, LLMConnectionError):
            return {
                "type": "error",
                "message": (
                    "Das Sprachmodell konnte keine gültige Aktion erzeugen. "
                    "Bitte formuliere deine Anfrage neu."
                ),
            }

    # 6. Aktion ausführen
    action = parsed["action"]
    spec = parsed["spec"]
    explanation = parsed["explanation"]

    if action == "execute":
        executor = PipelineExecutor(
            data_path=data_path or settings.data_path,
            artifacts_path=artifacts_path or settings.artifacts_path,
        )
        result = executor.execute(spec=spec, session_id=session_id, db_path=db_path)
        if "error" in result:
            return {"type": "error", "message": result.get("detail", result.get("error"))}
        return {"type": "result", "run_id": result["run_id"], "explanation": explanation}

    # action == "propose"
    return {
        "type": "proposal",
        "steps": spec.get("steps", []),
        "explanation": explanation,
        "confirmation_required": True,
    }
