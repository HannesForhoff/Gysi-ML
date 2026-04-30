import json
import logging
import uuid
from datetime import datetime, timezone

import jsonschema
import pandas as pd

from gysi_ml.executor.pipeline_context import PipelineContext
from gysi_ml.executor.spec_validator import SpecOrderError, validate_spec_order
from gysi_ml.persistence import artifact_repository, run_repository, spec_repository
from gysi_ml.persistence.database import get_connection
from gysi_ml.spec.schema import validate_spec
from gysi_ml.steps.registry import get_step_class
from gysi_ml.services.snapshot_service import SnapshotService
from gysi_ml.utils.data_loader import load_bikes_dataset

logger = logging.getLogger(__name__)


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
        started_at = _utc_now()

        # 3. Spec-Version speichern (automatische Versionsnummer)
        spec_entry = spec_repository.create_spec_version(
            session_id=session_id, spec=spec, db_path=db_path,
        )
        spec_id = spec_entry["spec_id"]
        spec_version = spec_entry["version"]

        pipeline_result = self._run_pipeline(
            spec=spec, run_id=run_id, spec_id=spec_id,
            spec_version=spec_version,
            session_id=session_id, started_at=started_at, db_path=db_path,
        )
        if "error" not in pipeline_result:
            pipeline_result["spec_version"] = spec_version
            pipeline_result["spec"] = spec
        return pipeline_result

    def execute_with_spec_id(
        self, spec: dict, spec_id: str, session_id: str, db_path: str | None = None
    ) -> dict:
        """Re-Execute mit einer bestehenden spec_id (kein neuer spec_versions-Eintrag)."""
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
        started_at = _utc_now()

        return self._run_pipeline(
            spec=spec, run_id=run_id, spec_id=spec_id,
            spec_version=None,
            session_id=session_id, started_at=started_at, db_path=db_path,
        )

    def _run_pipeline(
        self,
        spec: dict,
        run_id: str,
        spec_id: str,
        spec_version: str | None,
        session_id: str,
        started_at: str,
        db_path: str | None = None,
    ) -> dict:
        steps = spec.get("steps", [])

        # Resolve spec_version from DB if not provided (re-execution)
        if spec_version is None:
            conn = get_connection(db_path)
            try:
                row = conn.execute(
                    "SELECT version FROM spec_versions WHERE spec_id = ?",
                    (spec_id,),
                ).fetchone()
                spec_version = row["version"] if row else "v1"
            finally:
                conn.close()

        # 4. Run anlegen (running)
        run_repository.create_run(
            session_id=session_id,
            run_id=run_id,
            spec_id=spec_id,
            spec_version=spec_version,
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
                    # Pre-Split: leerer Test-DataFrame verhindert Doppelzählung in Metadata (Bug 1B)
                    result_train, _ = step.transform(
                        context.df_full, pd.DataFrame(columns=context.df_full.columns)
                    )
                    context.df_full = result_train
                metadata = step.get_metadata()
                context.add_step_result(step_type, metadata)
                if "metrics" in metadata and metadata["metrics"]:
                    context.metrics.update(metadata["metrics"])
                # Artefakt generieren (optional — Modeling- und SplitStep überschreiben diese Methode)
                artifact_info = step.generate_artifact(
                    artifacts_path=self._artifacts_path,
                    run_id=run_id,
                )
                # Normalisieren: dict → [dict], None → []
                if isinstance(artifact_info, list):
                    artifact_items = artifact_info
                elif isinstance(artifact_info, dict):
                    artifact_items = [artifact_info]
                else:
                    artifact_items = []
                for item in artifact_items:
                    artifact_id = str(uuid.uuid4())
                    artifact_created_at = _utc_now()
                    artifact_repository.create_artifact(
                        artifact_id=artifact_id,
                        run_id=run_id,
                        artifact_type=item["type"],
                        file_path=item["file_path"],
                        created_at=artifact_created_at,
                        db_path=db_path,
                    )
                    artifact_entry: dict = {
                        "artifact_id": artifact_id,
                        "type": item["type"],
                        "created_at": artifact_created_at,
                    }
                    # Optionales Label (z.B. von plot_distribution für feature-spezifischen Titel)
                    if "label" in item:
                        artifact_entry["label"] = item["label"]
                    context.artifacts.append(artifact_entry)
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

        # 8. Snapshot speichern (fire-and-forget — darf Run nicht zum Scheitern bringen)
        try:
            SnapshotService().save_snapshot(
                run_id=run_id,
                df=context.df_full,
                is_split=context.is_split,
                artifacts_path=self._artifacts_path,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Snapshot konnte nicht gespeichert werden (run_id=%s): %s", run_id, exc)

        return {
            "run_id": run_id,
            "status": "completed",
            "result": result,
        }
