import json
import uuid
from datetime import datetime, timezone

import jsonschema

from gysi_ml.executor.pipeline_context import PipelineContext
from gysi_ml.persistence import run_repository
from gysi_ml.spec.schema import validate_spec
from gysi_ml.steps.registry import get_step_class
from gysi_ml.utils.data_loader import load_bikes_dataset


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PipelineExecutor:
    def __init__(self, data_path: str) -> None:
        self._data_path = data_path

    def execute(self, spec: dict, session_id: str, db_path: str | None = None) -> dict:
        # 1. Spec validieren
        try:
            validate_spec(spec)
        except jsonschema.ValidationError as exc:
            return {
                "error": "invalid_spec",
                "detail": exc.message,
                "code": "INVALID_SPEC",
            }

        run_id = str(uuid.uuid4())
        spec_id = str(uuid.uuid4())
        started_at = _utc_now()

        # 2. Run anlegen (running)
        run_repository.create_run(
            session_id=session_id,
            run_id=run_id,
            spec_version="v1",
            status="running",
            started_at=started_at,
            db_path=db_path,
        )

        # 3. Datensatz laden
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

        # 4. Steps ausführen
        steps = spec.get("steps", [])
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

            # Prüfen ob Step einen vorherigen Split erfordert
            if getattr(step_cls, "requires_split", False) and not context.is_split:
                finished_at = _utc_now()
                run_repository.update_run_status(
                    run_id=run_id,
                    status="failed",
                    finished_at=finished_at,
                    error_message=f"Step '{step_type}' benötigt einen vorherigen 'split'-Step.",
                    db_path=db_path,
                )
                return {
                    "error": "split_required",
                    "detail": f"Step '{step_type}' benötigt einen vorherigen 'split'-Step.",
                    "code": "SPLIT_REQUIRED",
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
                context.add_step_result(step_type, step.get_metadata())
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

        # 5. Run auf completed setzen
        finished_at = _utc_now()
        result = {"step_results": context.step_results}
        run_repository.update_run_status(
            run_id=run_id,
            status="completed",
            finished_at=finished_at,
            result_json=json.dumps(result),
            db_path=db_path,
        )

        # 6. Spec-Version speichern
        run_repository.save_spec_version(
            spec_id=spec_id,
            session_id=session_id,
            version="v1",
            spec_json=json.dumps(spec),
            created_at=finished_at,
            db_path=db_path,
        )

        return {
            "run_id": run_id,
            "status": "completed",
            "result": result,
        }
