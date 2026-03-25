import json

import jsonschema

from gysi_ml.config import get_settings
from gysi_ml.core.capabilities import get_capabilities
from gysi_ml.executor.executor import PipelineExecutor
from gysi_ml.executor.spec_validator import SpecOrderError, validate_spec_order
from gysi_ml.llm.client import call_llm
from gysi_ml.llm.exceptions import LLMConnectionError, LLMResponseValidationError
from gysi_ml.llm.prompts import build_retry_prompt, build_system_prompt
from gysi_ml.llm.response_schema import validate_llm_response
from gysi_ml.persistence import message_repository, proposal_repository, spec_repository, step_state_repository
from gysi_ml.spec.schema import validate_spec

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
    current_spec_entry = spec_repository.get_latest_spec(
        session_id=session_id, db_path=db_path
    )
    current_spec = current_spec_entry["spec"] if current_spec_entry else None
    system_prompt = build_system_prompt(capabilities, current_spec=current_spec)

    # 3. Gesprächshistorie laden und messages-Array aufbauen
    history = message_repository.get_messages_for_session(
        session_id=session_id, db_path=db_path
    )
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # 3b. Offene Proposals vor dem LLM-Aufruf implizit ablehnen
    proposal_repository.reject_pending_proposals(session_id=session_id, db_path=db_path)

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
    spec_version_ref = parsed.get("spec_version")

    if action == "rollback":
        target_spec_id = parsed.get("target_spec_id")
        if not target_spec_id:
            return {"type": "error", "message": "Rollback: target_spec_id fehlt."}
        new_spec = spec_repository.rollback_to(
            session_id=session_id, target_spec_id=target_spec_id, db_path=db_path
        )
        if new_spec is None:
            return {"type": "error", "message": f"Spec '{target_spec_id}' nicht gefunden."}
        return {
            "type": "rollback",
            "new_spec_id": new_spec["spec_id"],
            "new_version": new_spec["version"],
            "change_summary": new_spec["change_summary"],
        }

    if action == "compare_runs":
        run_id_a = parsed.get("run_id_a")
        run_id_b = parsed.get("run_id_b")
        if not run_id_a or not run_id_b:
            return {"type": "error", "message": "Zwei Run-IDs für den Vergleich erforderlich."}

        from gysi_ml.persistence import run_repository

        run_a = run_repository.get_run(run_id_a, db_path=db_path)
        run_b = run_repository.get_run(run_id_b, db_path=db_path)

        if run_a is None or run_a.get("session_id") != session_id:
            return {"type": "error", "message": f"Run '{run_id_a}' nicht gefunden."}
        if run_b is None or run_b.get("session_id") != session_id:
            return {"type": "error", "message": f"Run '{run_id_b}' nicht gefunden."}

        def _extract_metrics(run: dict) -> dict | None:
            result = run.get("result") or {}
            return result.get("metrics") or None

        metrics_a = _extract_metrics(run_a)
        metrics_b = _extract_metrics(run_b)

        better_run_id = None
        if metrics_a and metrics_b:
            r2_a = metrics_a.get("r2", float("-inf"))
            r2_b = metrics_b.get("r2", float("-inf"))
            better_run_id = run_id_a if r2_a >= r2_b else run_id_b

        return {
            "type": "comparison",
            "runs": [
                {"run_id": run_id_a, "status": run_a["status"], "metrics": metrics_a},
                {"run_id": run_id_b, "status": run_b["status"], "metrics": metrics_b},
            ],
            "better_run_id": better_run_id,
            "explanation": explanation,
        }

    if action == "modify_spec":
        # Neue Spec validieren
        try:
            validate_spec(spec)
        except jsonschema.ValidationError as exc:
            return {"type": "error", "message": f"Ungültige Spec: {exc.message}"}
        # Spec-Reihenfolge validieren
        try:
            validate_spec_order(spec.get("steps", []))
        except SpecOrderError as exc:
            return {"type": "error", "message": str(exc)}
        # Neue Spec-Version anlegen
        spec_entry = spec_repository.create_spec_version(
            session_id=session_id, spec=spec, db_path=db_path
        )
        return {
            "type": "spec_updated",
            "spec_id": spec_entry["spec_id"],
            "version": spec_entry["version"],
            "spec": spec_entry["spec"],
            "explanation": explanation,
        }

    if action == "execute":
        executor = PipelineExecutor(
            data_path=data_path or settings.data_path,
            artifacts_path=artifacts_path or settings.artifacts_path,
        )

        if spec_version_ref:
            existing_spec = spec_repository.get_spec_by_version(
                session_id=session_id, version=spec_version_ref, db_path=db_path
            )
            if existing_spec is None:
                return {
                    "type": "error",
                    "message": f"Spec-Version '{spec_version_ref}' nicht gefunden.",
                }
            result = executor.execute_with_spec_id(
                spec=existing_spec["spec"],
                spec_id=existing_spec["spec_id"],
                session_id=session_id,
                db_path=db_path,
            )
        else:
            result = executor.execute(spec=spec, session_id=session_id, db_path=db_path)

        if "error" in result:
            return {"type": "error", "message": result.get("detail", result.get("error"))}
        return {"type": "result", "run_id": result["run_id"], "explanation": explanation}

    if action == "abort_step_by_step":
        state = step_state_repository.get_step_state_by_session(
            session_id=session_id, db_path=db_path
        )
        if state:
            completed = state["completed_steps"]
            step_state_repository.delete_step_state(
                state_id=state["state_id"], db_path=db_path
            )
            types_str = ", ".join(s["type"] for s in completed)
            return {
                "type": "assistant",
                "message": f"Step-by-Step-Modus beendet. Bisher ausgeführt: {types_str or 'keine Steps'}.",
            }
        return {"type": "assistant", "message": "Kein aktiver Step-by-Step-Vorgang."}

    # action == "propose"
    proposal = proposal_repository.create_proposal(
        session_id=session_id,
        spec_json=json.dumps(spec),
        explanation=explanation,
        db_path=db_path,
    )
    return {
        "type": "proposal",
        "proposal_id": proposal["proposal_id"],
        "steps": spec.get("steps", []),
        "explanation": explanation,
        "confirmation_required": True,
    }
