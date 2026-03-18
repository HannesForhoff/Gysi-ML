import json

from gysi_ml.config import get_settings
from gysi_ml.executor.executor import PipelineExecutor
from gysi_ml.persistence import proposal_repository


def confirm_proposal(
    session_id: str,
    proposal_id: str,
    db_path: str | None = None,
    data_path: str | None = None,
    artifacts_path: str | None = None,
) -> dict:
    """Bestätigt und führt einen offenen Proposal aus.

    Returns:
        dict mit 'type' und 'run_id' bei Erfolg, oder Fehler-dict.
    """
    settings = get_settings()

    # 1. Proposal laden und Session-Zugehörigkeit prüfen
    proposal = proposal_repository.get_proposal(proposal_id=proposal_id, db_path=db_path)
    if proposal is None or proposal["session_id"] != session_id:
        return {"error": "proposal_not_found"}

    # 2. Status prüfen — nur pending Proposals dürfen bestätigt werden
    if proposal["status"] != "pending":
        return {"error": "no_pending_proposal"}

    # 3. Proposal-Status → confirmed
    proposal_repository.update_proposal_status(
        proposal_id=proposal_id, status="confirmed", db_path=db_path
    )

    # 4. Spec aus Proposal laden und ausführen
    spec = json.loads(proposal["spec_json"])
    executor = PipelineExecutor(
        data_path=data_path or settings.data_path,
        artifacts_path=artifacts_path or settings.artifacts_path,
    )
    result = executor.execute(spec=spec, session_id=session_id, db_path=db_path)

    if "error" in result:
        return {
            "type": "error",
            "message": result.get("detail", result.get("error")),
        }
    return {
        "type": "result",
        "run_id": result["run_id"],
        "explanation": "Proposal bestätigt und ausgeführt.",
    }
