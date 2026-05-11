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
from gysi_ml.persistence import message_repository, proposal_repository, run_repository, spec_repository, step_state_repository
from gysi_ml.spec.schema import validate_spec

log = logging.getLogger(__name__)

LLM_NOT_CONFIGURED = "llm_not_configured"

# Steps die keine Daten verändern — werden ausgeführt, aber nicht in die
# akkumulierte Session-Spec aufgenommen und erzeugen keine neue Spec-Version.
TRANSIENT_STEP_TYPES: frozenset[str] = frozenset({"plot_distribution"})

# Preprocessing-Steps, die statistische Parameter aus dem Datensatz lernen (fit/transform).
# Diese dürfen nur NACH dem Train/Test-Split ausgeführt werden, sonst Data Leakage.
_LEARNABLE_STEP_TYPES: frozenset[str] = frozenset({
    "impute_missing", "encode_categorical", "outlier_handling", "rare_category_bucketing"
})


def _get_suggested_next_steps(spec: dict | None) -> list[str]:
    """Deterministische Nächste-Schritte-Vorschläge für Einsteiger.

    Jeder Vorschlag entspricht genau einem Pipeline-Step — keine Bündel,
    keine vagen Sammelanfragen. Das LLM führt immer nur einen Step aus.
    """
    if spec is None:
        return []
    steps = spec.get("steps", [])
    done = {s.get("type") for s in steps if s.get("enabled", True)}
    if not done:
        return []

    has_split = "split" in done
    has_model = bool(done & {"train_decision_tree", "train_ebm"})

    suggestions: list[str] = []

    if not has_split:
        # Vorschläge streng als einzelne nächste sinnvolle Schritte
        if "dedup" not in done:
            suggestions.append("Entferne doppelte Zeilen aus dem Datensatz")
        elif "impute_missing" not in done:
            suggestions.append("Fülle fehlende Werte in windspeed mit dem Median auf")
        if "time_feature_encoding" not in done:
            suggestions.append("Wandle die Datumsspalte dteday in Zeitfeatures um")
        if len(suggestions) < 3:
            suggestions.append("Teile die Daten 80/20 in Trainings- und Testdaten auf")
    elif not has_model:
        suggestions.append("Trainiere einen Decision Tree auf die Zielspalte cnt")
        if "catboost_feature_selection" not in done:
            suggestions.append("Welche Spalten haben den größten Einfluss auf cnt?")
    else:
        if "train_ebm" not in done and "train_decision_tree" in done:
            suggestions.append("Trainiere ein EBM-Modell zum Vergleich mit dem Decision Tree")
        if "catboost_feature_selection" not in done:
            suggestions.append("Welche Spalten haben den größten Einfluss auf cnt?")
        suggestions.append("Erkläre mir das Ergebnis des Modells")

    return suggestions[:3]


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

    def _merge_key(step: dict) -> str:
        """Eindeutiger Merge-Schlüssel für einen Step.

        impute_missing: Typ + Strategie → verschiedene Strategien sind separate Steps.
        Alle anderen Step-Typen: nur der Typ (pro Typ max. ein Eintrag).
        """
        if step.get("type") == "impute_missing":
            strategy = step.get("params", {}).get("strategy", "median")
            return f"impute_missing:{strategy}"
        return step.get("type", "")

    # Map: merge_key → Index in merged (für O(1)-Lookup)
    key_to_idx: dict[str, int] = {
        _merge_key(s): i for i, s in enumerate(current_steps)
    }

    merged: list[dict] = list(current_steps)
    for new_step in new_steps:
        step_type = new_step.get("type")
        if not step_type:
            # Ungültiger Step ohne type-Feld — wird vom Spec-Validator abgefangen
            merged.append(new_step)
            continue
        key = _merge_key(new_step)
        if key in key_to_idx:
            existing = merged[key_to_idx[key]]
            new_columns = new_step.get("params", {}).get("columns") or []
            existing_columns = existing.get("params", {}).get("columns") or []

            if new_columns and existing_columns:
                if isinstance(new_columns, dict) and isinstance(existing_columns, dict):
                    # Dict-Merge für Steps wie cast_dtype: {col: dtype}.
                    # Bestehende Einträge bleiben erhalten; neue Spalten werden hinzugefügt.
                    # Für gleiche Spalte ÜBERSCHREIBT der neue Wert den alten
                    # (User hat explizit neuen Typ angefordert).
                    merged_columns = {**existing_columns, **new_columns}
                else:
                    # Listen-Merge für Steps wie impute_missing: [col1, col2].
                    # Reihenfolge beibehalten, Duplikate entfernen.
                    merged_columns = list(dict.fromkeys(
                        (existing_columns if isinstance(existing_columns, list) else [])
                        + (new_columns if isinstance(new_columns, list) else [])
                    ))
                merged_params = {**existing.get("params", {}), "columns": merged_columns}
                merged[key_to_idx[key]] = {**existing, "params": merged_params}
            else:
                # Kein Spalten-Merge möglich → bestehenden Step ersetzen
                merged[key_to_idx[key]] = new_step
        else:
            # Neuer Key → Abhängigkeits-aware Einfügen.
            # cast_dtype muss immer VOR encode_categorical stehen, damit
            # Typ-Konvertierungen vor dem Encoding wirksam sind.
            if step_type == "cast_dtype" and "encode_categorical" in key_to_idx:
                encode_idx = key_to_idx["encode_categorical"]
                merged.insert(encode_idx, new_step)
                # Alle Indizes >= encode_idx um 1 verschieben
                for k in key_to_idx:
                    if key_to_idx[k] >= encode_idx:
                        key_to_idx[k] += 1
                key_to_idx[key] = encode_idx
            else:
                key_to_idx[key] = len(merged)
                merged.append(new_step)

    return {**new_spec, "steps": merged}


def _detect_leakage_risk(new_step_types: set[str], merged_steps: list[dict]) -> list[str]:
    """Gibt Liste der Step-Typen zurück, die in diesem Commit Data Leakage verursachen würden.

    Warnung wird ausgelöst wenn:
    - Ein Split hinzugefügt wird UND lernende Steps bereits vor dem Split liegen, ODER
    - Ein lernender Step vor dem Split hinzugefügt/modifiziert wird.

    Args:
        new_step_types: Set der Step-Typen die in diesem Execute-Aufruf neu hinzukommen.
        merged_steps: Vollständige Step-Liste nach dem spekulativen Merge.
    """
    split_idx = next((i for i, s in enumerate(merged_steps) if s.get("type") == "split"), None)
    if split_idx is None:
        return []  # kein Split → kein Leakage-Risiko (kein Test-Set)

    before_split_types = {s.get("type") for s in merged_steps[:split_idx]}
    learnable_before = sorted(before_split_types & _LEARNABLE_STEP_TYPES)

    if not learnable_before:
        return []

    # Nur warnen wenn dieser Call ursächlich ist:
    # (a) Der Split wird gerade hinzugefügt → lernende Steps liegen bereits davor, ODER
    # (b) Ein lernender Step vor dem Split wird gerade hinzugefügt/modifiziert
    this_call_is_responsible = bool(
        "split" in new_step_types
        or (new_step_types & _LEARNABLE_STEP_TYPES & before_split_types)
    )
    return learnable_before if this_call_is_responsible else []


def _step_result_is_effective(step_result: dict) -> bool:
    """True wenn ein einzelner Step-Result tatsächlich Daten verändert hat.

    Spiegelt die Effektivitätsprüfung aus executor._step_is_effective,
    angewandt auf Step-Results im message_service-Kontext.

    Bekannte No-Op-Fälle:
    - encode_categorical mit encoded_columns=[] (Spalte hatte falschen Dtype)
    - correlation_filter mit analysis_only=True (nur Analyse, kein Feature entfernt)
    - catboost_feature_selection mit analysis_only=True (nur Analyse, kein Feature entfernt)
    """
    step_type = step_result.get("step_type", "")
    metadata = step_result.get("metadata", {}) or {}
    if step_type == "encode_categorical":
        return bool(metadata.get("encoded_columns"))
    if step_type in ("correlation_filter", "catboost_feature_selection"):
        return not metadata.get("analysis_only", False)
    return True


def _new_persistent_steps_are_effective(
    new_step_results: list[dict], new_step_types: set[str]
) -> bool:
    """True wenn mindestens ein neu hinzugefügter persistenter Step wirksam war.

    - Leeres new_step_types → Re-Run → immer True.
    - Leere new_step_results bei vorhandenen new_step_types → konservativ True
      (keine Metadaten verfügbar, z.B. in Mocks ohne vollständigen Run-Stack).
    """
    if not new_step_types:
        return True  # Re-Run: Spec unverändert, trotzdem ausführen
    if not new_step_results:
        return True  # konservativ: keine Metadaten → wirksam annehmen
    return any(_step_result_is_effective(sr) for sr in new_step_results)


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
    spec_history = spec_repository.get_all_specs_for_session(
        session_id=session_id, db_path=db_path
    )
    df_stats = _compute_column_stats(data_path or settings.data_path)
    system_prompt = build_system_prompt(
        capabilities,
        current_spec=current_spec,
        df_stats=df_stats,
        spec_history=spec_history or None,
    )

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
        target_version = parsed.get("target_version")

        if target_version:
            resolved_id = spec_repository.get_spec_id_by_version(
                session_id=session_id, version=target_version, db_path=db_path
            )
            if not resolved_id:
                return {"type": "error", "message": f"Version '{target_version}' nicht gefunden."}
            target_spec_id = resolved_id

        if not target_spec_id:
            return {"type": "error", "message": "Rollback: target_version oder target_spec_id fehlt."}

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
        _effective = True  # ob der Run tatsächlich Daten verändert hat (No-Op-Erkennung)
        # parameters_summary ist Präsentationsschicht — darf nicht in die ausführbare Spec.
        # PIPELINE_SPEC_SCHEMA hat additionalProperties: False, weshalb validate_spec sonst fehlschlägt.
        raw_steps = spec.get("steps", [])  # vor Bereinigung sichern (enthält parameters_summary für Anzeige)
        clean_steps = [{k: v for k, v in s.items() if k != "parameters_summary"} for s in raw_steps]
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
            # Transiente Steps (z.B. plot_distribution) ändern keine Daten — sie werden
            # ausgeführt, aber nicht in die akkumulierte Session-Spec aufgenommen.
            # Dadurch entsteht keine neue Spec-Version wenn nur Plots angefordert werden.
            persistent_steps = [s for s in clean_steps if s.get("type") not in TRANSIENT_STEP_TYPES]
            transient_steps = [s for s in clean_steps if s.get("type") in TRANSIENT_STEP_TYPES]

            # Nur persistente Steps mit der akkumulierten Session-Spec zusammenführen
            persistent_spec = {**spec, "steps": persistent_steps}
            try:
                merged_persistent = _merge_specs(current_spec, persistent_spec)
            except Exception as exc:  # pragma: no cover
                log.exception("Spec-Merge fehlgeschlagen")
                return {
                    "type": "error",
                    "message": f"Interner Fehler beim Zusammenführen der Pipeline-Spec: {exc}",
                }

            # Data-Leakage-Risikocheck: lernende Steps vor dem Split?
            new_persistent_types = {s.get("type") for s in persistent_steps}
            leakage_at_risk = _detect_leakage_risk(new_persistent_types, merged_persistent.get("steps", []))
            if leakage_at_risk:
                # Statt ausführen: Vorschlag mit roter Warnung — Nutzer muss bewusst bestätigen
                raw_persistent_for_display = [
                    s for s in raw_steps if s.get("type") not in TRANSIENT_STEP_TYPES
                ]
                clean_proposal_spec = {**spec, "steps": persistent_steps}
                leakage_proposal = proposal_repository.create_proposal(
                    session_id=session_id,
                    spec_json=json.dumps(clean_proposal_spec),
                    explanation=explanation,
                    db_path=db_path,
                )
                return {
                    "type": "proposal",
                    "proposal_id": leakage_proposal["proposal_id"],
                    "steps": raw_persistent_for_display,
                    "explanation": explanation,
                    "data_leakage_warning": True,
                    "leakage_steps": leakage_at_risk,
                }

            # Ausführungs-Spec: persistente Steps + transiente Steps ans Ende
            exec_spec = {**merged_persistent, "steps": merged_persistent.get("steps", []) + transient_steps}

            _effective = True  # Default: wirksam (überschrieben wenn No-Op erkannt)
            if persistent_steps or current_spec_entry is None:
                # Spec-Version wird erst nach erfolgreicher Ausführung gespeichert, damit
                # fehlgeschlagene Runs die Session-Spec nicht korrumpieren (Bug 1F).
                tentative_spec_id = current_spec_entry["spec_id"] if current_spec_entry else None
                result = executor.execute_with_spec_id(
                    spec=exec_spec,
                    spec_id=tentative_spec_id,
                    session_id=session_id,
                    db_path=db_path,
                )
                spec_for_response = merged_persistent
                if "error" not in result:
                    # Neu hinzugefügte persistente Steps auf Wirksamkeit prüfen — No-Ops
                    # erzeugen keine neue Spec-Version (z.B. encode_categorical auf int64).
                    _exec_step_results = result.get("result", {}).get("step_results", [])
                    _new_exec_results = [
                        r for r in _exec_step_results
                        if r.get("step_type") in new_persistent_types
                    ]
                    _effective = _new_persistent_steps_are_effective(_new_exec_results, new_persistent_types)
                    if _effective:
                        spec_entry = spec_repository.create_spec_version(
                            session_id=session_id, spec=merged_persistent, db_path=db_path
                        )
                        run_repository.update_run_spec_ref(
                            run_id=result["run_id"],
                            spec_id=spec_entry["spec_id"],
                            spec_version=spec_entry["version"],
                            db_path=db_path,
                        )
                        version_for_response = spec_entry["version"]
                    else:
                        # Alle neuen Steps waren No-Ops → keine neue Spec-Version anlegen,
                        # Anzeige auf bisherigem Stand lassen.
                        version_for_response = current_spec_entry["version"] if current_spec_entry else None
                        spec_for_response = current_spec_entry["spec"] if current_spec_entry else {}
                else:
                    version_for_response = current_spec_entry["version"] if current_spec_entry else None
            else:
                # Nur transiente Steps (z.B. plot_distribution): keine neue Spec-Version.
                # Basisknoten verwenden — falls noch keiner existiert (alte Session), jetzt anlegen.
                if current_spec_entry is None:
                    current_spec_entry = spec_repository.create_spec_version(
                        session_id=session_id, spec={"steps": []}, db_path=db_path
                    )
                result = executor.execute_with_spec_id(
                    spec=exec_spec,
                    spec_id=current_spec_entry["spec_id"],
                    session_id=session_id,
                    db_path=db_path,
                )
                spec_for_response = merged_persistent
                version_for_response = current_spec_entry["version"]

            full_exec_spec = exec_spec

        if "error" in result:
            return {"type": "error", "message": result.get("detail", result.get("error"))}
        run_result = result.get("result", {})
        step_results = run_result.get("step_results", [])

        # Post-Run-Erklärung: zweiter LLM-Call mit echten Ergebnissen (Bug 1.11)
        # Nur die neuen/geänderten Steps übergeben — nie die gesamte akkumulierte Pipeline.
        # "clean_steps" enthält exakt die Steps die der Nutzer in dieser Anfrage angefragt hat.
        # Fallback bei Re-Run (clean_steps leer): alle Steps verwenden.
        new_step_types = {s["type"] for s in clean_steps}
        # Für die Post-Run-Erklärung die vollständige Ausführungs-Spec verwenden
        # (inkl. transienter Steps wie plot_distribution, die nicht in spec_for_response stehen)
        explanation_base_spec = locals().get("full_exec_spec", spec_for_response)
        if new_step_types:
            new_step_results = [r for r in step_results if r.get("step_type") in new_step_types]
            new_steps_spec = {**explanation_base_spec, "steps": [
                s for s in explanation_base_spec.get("steps", []) if s.get("type") in new_step_types
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
                full_spec=explanation_base_spec,
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

        # Bei No-Op-Runs (z.B. catboost_feature_selection mit analysis_only=True) keine
        # Artefakte zurückgeben — die Daten haben sich nicht geändert, redundante
        # train/test-CSVs sollen nicht im Frontend erscheinen.
        _run_artifacts = run_result.get("artifacts", []) if _effective else []
        enriched_artifacts = [
            {**a, "run_id": result["run_id"], "spec_version": version_for_response}
            for a in _run_artifacts
        ]
        suggested_next_steps = _get_suggested_next_steps(spec_for_response)
        return {
            "type": "result",
            "run_id": result["run_id"],
            "explanation": explanation,
            "post_run_explanation": post_run_explanation,
            "step_results": step_results,
            "metrics": run_result.get("metrics") or None,
            "artifacts": enriched_artifacts,
            "spec": spec_for_response,
            "version": version_for_response,
            "suggested_next_steps": suggested_next_steps,
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
