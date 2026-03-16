import json
import uuid
from datetime import datetime, timezone

import jsonschema

from gysi_ml.executor.pipeline_context import PipelineContext
from gysi_ml.executor.spec_validator import SpecOrderError, validate_spec_order
from gysi_ml.persistence import artifact_repository, run_repository
from gysi_ml.spec.schema import validate_spec
from gysi_ml.steps.registry import get_step_class
from gysi_ml.utils.data_loader import load_bikes_dataset


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PipelineExecutor:
    def __init__(self, data_path: str, artifacts_path: str = "../artifacts") -> None:
        self._data_path = data_path
        self._artifacts_path = artifacts_path

    def execute(self, spec: dict, session_id: str, db_path: str | None = None) -> dict:
        # 1. Spec-Struktur validieren
        try:
            validate_spec(spec)
        except jsonschema.ValidationError as exc:
            return {
                "error": "invalid_spec",
                "detail": exc.message,
                "code": "INVALID_SPEC",
            }

        # 2. Spec-Reihenfolge validieren (vor Ausführung)
        steps = spec.get("steps", [])
        try:
            validate_spec_order(steps)
        except SpecOrderError as exc:
            return {
                "error": "invalid_spec_order",
                "detail": str(exc),
                "code": "INVALID_SPEC_ORDER",
            }

        run_id = str(uuid.uuid4())
        spec_id = str(uuid.uuid4())
        started_at = _utc_now()

        # 3. Spec-Version speichern (vor Ausführung, damit auch fehlgeschlagene Runs eine Spec haben)
        run_repository.save_spec_version(
            spec_id=spec_id,
            session_id=session_id,
            version="v1",
            spec_json=json.dumps(spec),
            created_at=started_at,
            db_path=db_path,
        )

        # 4. Run anlegen (running)
        run_repository.create_run(
            session_id=session_id,
            run_id=run_id,
            spec_id=spec_id,
            spec_version="v1",
            status="running",
            started_at=started_at,
            db_path=db_path,
        )

        # 5. Datensatz laden
        try:
            df = load_bikes_dataset(self._data_path)
        except Exception as exc:
            finished_at = _utc_now()
            run_repository.update_run_status(
                run_id=run_id,
                status="failed",
                finished_at=finished_at,
                error_message=str(exc),
                db_path=db_path,
            )
            return {
                "error": "data_load_failed",
                "detail": str(exc),
                "code": "DATA_LOAD_FAILED",
            }

        context = PipelineContext(df_full=df)

        # 6. Steps ausführen
        for step_spec in steps:
            step_type = step_spec["type"]
            enabled = step_spec.get("enabled", True)
            if not enabled:
                continue

            params = step_spec.get("params", {})

            try:
                step_cls = get_step_class(step_type)
            except KeyError:
                finished_at = _utc_now()
                run_repository.update_run_status(
                    run_id=run_id,
                    status="failed",
                    finished_at=finished_at,
                    error_message=f"Unbekannter Step-Typ: '{step_type}'",
                    db_path=db_path,
                )
                return {
                    "error": "unknown_step_type",
                    "detail": f"Step-Typ '{step_type}' ist nicht registriert.",
                    "code": "UNKNOWN_STEP_TYPE",
                }

            # Prüfen ob Step einen vorherigen Split erfordert (Fallback für Steps
            # mit requires_split=True die nicht in spec_validator.REQUIRES_SPLIT stehen)
            if getattr(step_cls, "requires_split", False) and not context.is_split:
                finished_at = _utc_now()
                msg = f"Step '{step_type}' benötigt einen vorherigen 'split'-Step."
                run_repository.update_run_status(
                    run_id=run_id,
                    status="failed",
                    finished_at=finished_at,
                    error_message=msg,
                    db_path=db_path,
                )
                return {
                    "error": "invalid_spec_order",
                    "detail": msg,
                    "code": "INVALID_SPEC_ORDER",
                }

            try:
                step = step_cls(params=params)
                if getattr(step_cls, "is_splitter", False):
                    # Split-Step: teilt df_full in df_train/df_test
                    step.fit(context.df_full)
                    context.df_train, context.df_test = step.transform(
                        context.df_full, context.df_full
                    )
                    context.is_split = True
                elif context.is_split:
                    step.fit(context.df_train)
                    context.df_train, context.df_test = step.transform(
                        context.df_train, context.df_test
                    )
                else:
                    step.fit(context.df_full)
                    result_train, _ = step.transform(
                        context.df_full, context.df_full
                    )
                    context.df_full = result_train
                metadata = step.get_metadata()
                context.add_step_result(step_type, metadata)
                if "metrics" in metadata and metadata["metrics"]:
                    context.metrics.update(metadata["metrics"])
                # Artefakt generieren (optional — nur Modeling-Steps überschreiben diese Methode)
                artifact_info = step.generate_artifact(
                    artifacts_path=self._artifacts_path,
                    run_id=run_id,
                )
                if artifact_info:
                    artifact_id = str(uuid.uuid4())
                    artifact_created_at = _utc_now()
                    artifact_repository.create_artifact(
                        artifact_id=artifact_id,
                        run_id=run_id,
                        artifact_type=artifact_info["type"],
                        file_path=artifact_info["file_path"],
                        created_at=artifact_created_at,
                        db_path=db_path,
                    )
                    context.artifacts.append({
                        "artifact_id": artifact_id,
                        "type": artifact_info["type"],
                        "created_at": artifact_created_at,
                    })
            except Exception as exc:
                finished_at = _utc_now()
                run_repository.update_run_status(
                    run_id=run_id,
                    status="failed",
                    finished_at=finished_at,
                    error_message=str(exc),
                    db_path=db_path,
                )
                return {
                    "error": "step_execution_failed",
                    "detail": str(exc),
                    "code": "STEP_EXECUTION_FAILED",
                }

        # 7. Run auf completed setzen
        finished_at = _utc_now()
        result = {
            "step_results": context.step_results,
            "metrics": context.metrics,
            "artifacts": context.artifacts,
        }
        run_repository.update_run_status(
            run_id=run_id,
            status="completed",
            finished_at=finished_at,
            result_json=json.dumps(result),
            db_path=db_path,
        )

        return {
            "run_id": run_id,
            "status": "completed",
            "result": result,
        }
