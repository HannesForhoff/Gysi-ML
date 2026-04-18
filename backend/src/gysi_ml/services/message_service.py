import json
import logging

import jsonschema
import pandas as pd

from gysi_ml.config import get_settings
from gysi_ml.utils.data_loader import load_bikes_dataset
from gysi_ml.core.capabilities import get_capabilities
from gysi_ml.executor.executor import PipelineExecutor
from gysi_ml.executor.spec_validator import SpecOrderError, validate_spec_order
from gysi_ml.llm.client import call_llm
from gysi_ml.llm.exceptions import LLMConnectionError, LLMResponseValidationError
from gysi_ml.llm.prompts import build_post_run_prompt, build_retry_prompt, build_system_prompt
from gysi_ml.llm.response_schema import validate_llm_response
from gysi_ml.persistence import message_repository, proposal_repository, spec_repository, step_state_repository
from gysi_ml.spec.schema import validate_spec

log = logging.getLogger(__name__)

LLM_NOT_CONFIGURED = "llm_not_configured"


def _merge_specs(current_spec: dict | None, new_spec: dict) -> dict:
    """Fügt neue Steps aus new_spec in die bestehende Spec ein.

    Merge-Regeln:
    - Kein current_spec (Erstausführung) → new_spec unverändert
    - new_spec leer (steps: []) → aktuelle Spec erneut ausführen (Re-Run)
    - Neuer Step-Typ noch nicht in current_spec → am Ende anfügen
    - Step-Typ bereits vorhanden → durch neuen Step ersetzen (neue Parameter)

    Die Reihenfolge der bestehenden Steps bleibt erhalten. Neue Steps kommen
    stets NACH den bestehenden (abgesehen von Ersetzungen an der gleichen Position).
    """
    new_steps = new_spec.get("steps", [])

    # Kein aktueller Zustand: direkte Ausführung der LLM-Spec
    if current_spec is None:
        return new_spec

    current_steps: list[dict] = list(current_spec.get("steps", []))

    # Leere neue Spec = Re-Run des aktuellen Stands
    if not new_steps:
        return {**new_spec, "steps": current_steps}

    # Map: step_type → Index in current_steps (für O(1)-Lookup)
    type_to_idx: dict[str, int] = {
        s["type"]: i for i, s in enumerate(current_steps)
    }

    merged: list[dict] = list(current_steps)
    for new_step in new_steps:
        step_type = new_step.get("type")
        if not step_type:
            # Ungültiger Step ohne type-Feld — wird vom Spec-Validator abgefangen
            merged.append(new_step)
            continue
        if step_type in type_to_idx:
            # Step existiert bereits → Parameter aktualisieren, Position beibehalten
            merged[type_to_idx[step_type]] = new_step
        else:
            # Neuer Step-Typ → anhängen und in Index aufnehmen
            type_to_idx[step_type] = len(merged)
            merged.append(new_step)

    return {**new_spec, "steps": merged}


def _compute_column_stats(data_path: str) -> dict | None:
    """Berechnet deskriptive Statistiken pro Spalte für den System-Prompt (Bug 1D).

    Verhindert LLM-Halluzination bei Fragen zu konkreten Spaltenwerten.
    Gibt None zurück wenn das Laden des Datensatzes fehlschlägt.
    """
    try:
        df = load_bikes_dataset(data_path)
        stats: dict[str, dict] = {}
        for col in df.columns:
            col_stats: dict = {
                "dtype": str(df[col].dtype),
                "n_missing": int(df[col].isna().sum()),
            }
            if pd.api.types.is_numeric_dtype(df[col]):
                non_null = df[col].dropna()
                col_stats["median"] = round(float(non_null.median()), 4) if len(non_null) > 0 else None
                col_stats["mean"] = round(float(non_null.mean()), 4) if len(non_null) > 0 else None
                vc = non_null.value_counts()
                col_stats["most_frequent"] = float(vc.index[0]) if len(vc) > 0 else None
            stats[col] = col_stats
        return stats
    except Exception as exc:
        log.warning("Spaltenstatistiken konnten nicht berechnet werden: %s", exc)
        return None


def handle_message(
    session_id: str,
    text: str,
    db_path: str | None = None,
    data_path: str | None = None,
    artifacts_path: str | None = None,
    api_key: str | None = None,
    llm_model: str | None = None,
) -> dict:
    """Koordiniert den Nachrichtenfluss: Text -> LLM -> Ausführung/Proposal.

    Returns:
        dict mit Pflichtfeld 'type' ('proposal', 'result', 'error')
    """
    settings = get_settings()
    effective_api_key = api_key if api_key is not None else settings.openai_api_key
    effective_model = llm_model if llm_model is not None else settings.llm_model

    # 1. LLM-Konfiguration prüfen
    if not effective_api_key or not effective_model:
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
    df_stats = _compute_column_stats(data_path or settings.data_path)
    system_prompt = build_system_prompt(capabilities, current_spec=current_spec, df_stats=df_stats)

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
            model=effective_model,
            api_key=effective_api_key,
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
                model=effective_model,
                api_key=effective_api_key,
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

    # Reine Informationsanfragen: keine Ausführung, Antwort in explanation (Bug 1E-E2)
    if action == "info":
        return {
            "type": "assistant",
            "message": explanation,
        }

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
        # parameters_summary ist Präsentationsschicht — darf nicht in die ausführbare Spec.
        # PIPELINE_SPEC_SCHEMA hat additionalProperties: False, weshalb validate_spec sonst fehlschlägt.
        clean_steps = [{k: v for k, v in s.items() if k != "parameters_summary"} for s in spec.get("steps", [])]
        spec = {**spec, "steps": clean_steps}

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
            spec_for_response = existing_spec["spec"]
            version_for_response = existing_spec["version"]
        else:
            # Neue Steps mit akkumulierter Session-Spec zusammenführen,
            # damit der Executor immer die vollständige Pipeline erhält.
            try:
                merged_spec = _merge_specs(current_spec, spec)
            except Exception as exc:  # pragma: no cover
                log.exception("Spec-Merge fehlgeschlagen")
                return {
                    "type": "error",
                    "message": f"Interner Fehler beim Zusammenführen der Pipeline-Spec: {exc}",
                }
            result = executor.execute(spec=merged_spec, session_id=session_id, db_path=db_path)
            spec_for_response = result.get("spec", merged_spec)
            version_for_response = result.get("spec_version")

        if "error" in result:
            return {"type": "error", "message": result.get("detail", result.get("error"))}
        run_result = result.get("result", {})
        step_results = run_result.get("step_results", [])

        # Post-Run-Erklärung: zweiter LLM-Call mit echten Ergebnissen (Bug 1.11)
        # Nur die neuen/geänderten Steps übergeben — nie die gesamte akkumulierte Pipeline.
        # "clean_steps" enthält exakt die Steps die der Nutzer in dieser Anfrage angefragt hat.
        # Fallback bei Re-Run (clean_steps leer): alle Steps verwenden.
        new_step_types = {s["type"] for s in clean_steps}
        if new_step_types:
            new_step_results = [r for r in step_results if r.get("step_type") in new_step_types]
            new_steps_spec = {**spec_for_response, "steps": [
                s for s in spec_for_response.get("steps", []) if s.get("type") in new_step_types
            ]}
        else:
            # Re-Run: alle Steps erklären
            new_step_results = step_results
            new_steps_spec = spec_for_response

        post_run_explanation: str | None = None
        try:
            post_run_prompt = build_post_run_prompt(
                user_message=text,
                spec=new_steps_spec,
                step_results=new_step_results,
            )
            post_run_explanation = call_llm(
                messages=[
                    {"role": "user", "content": post_run_prompt},
                ],
                model=effective_model,
                api_key=effective_api_key,
                base_url=settings.openai_base_url or None,
            )
        except Exception as exc:
            log.warning("Post-Run-Erkl\u00e4rung fehlgeschlagen (nicht kritisch): %s", exc)

        return {
            "type": "result",
            "run_id": result["run_id"],
            "explanation": explanation,
            "post_run_explanation": post_run_explanation,
            "step_results": step_results,
            "artifacts": run_result.get("artifacts", []),
            "spec": spec_for_response,
            "version": version_for_response,
        }

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
    raw_steps = spec.get("steps", [])

    # Spec für Speicherung bereinigen: parameters_summary ist nur Präsentation,
    # darf nicht in der ausführbaren Spec landen (würde validate_spec bei Confirm fehlschlagen).
    clean_steps = [{k: v for k, v in s.items() if k != "parameters_summary"} for s in raw_steps]
    clean_spec = {**spec, "steps": clean_steps}

    proposal = proposal_repository.create_proposal(
        session_id=session_id,
        spec_json=json.dumps(clean_spec),
        explanation=explanation,
        db_path=db_path,
    )
    return {
        "type": "proposal",
        "proposal_id": proposal["proposal_id"],
        "steps": raw_steps,  # enthält parameters_summary für die Anzeige
        "explanation": explanation,
        "confirmation_required": True,
    }
