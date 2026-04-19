"""CommandService — Slash-Command-Router für /help, /overview, /status (Story 6.2)."""
from __future__ import annotations

from pathlib import Path

import yaml

KNOWN_COMMANDS = ["/help", "/overview", "/status"]


class CommandService:
    def is_slash_command(self, content: str) -> bool:
        return content.strip().startswith("/")

    def handle(self, content: str, session_id: str, db_path: str | None = None) -> str:
        parts = content.strip().split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else None

        if command == "/help":
            return self._handle_help(arg)
        elif command == "/overview":
            return self._handle_overview(session_id, db_path)
        elif command == "/status":
            return self._handle_status(session_id, db_path)
        else:
            return (
                f"Unbekannter Command: `{command}`\n\n"
                f"Verfügbare Commands: {', '.join(KNOWN_COMMANDS)}"
            )

    def _handle_help(self, topic: str | None) -> str:
        texts = self._load_help_texts()
        help_section = texts.get("help", {})
        if topic:
            categories = help_section.get("categories", {})
            key = topic.lower()
            if key in categories:
                return f"**{key}:** {categories[key]}"
            return f"Unbekanntes Thema: `{topic}`. Verf\u00fcgbar: {', '.join(categories.keys())}"
        full_text = help_section.get("full_text")
        if full_text:
            return full_text.strip()
        # Fallback: kategorie-basiert
        categories = help_section.get("categories", {})
        lines = ["**Gysi-Hilfe:**\n"]
        for cat, desc in categories.items():
            lines.append(f"- **{cat}:** {desc}")
        return "\n".join(lines)

    def _handle_overview(self, session_id: str, db_path: str | None) -> str:
        from gysi_ml.services.profiling_service import ProfilingService

        return ProfilingService().profile_current(session_id=session_id, db_path=db_path)

    def _handle_status(self, session_id: str, db_path: str | None) -> str:
        from gysi_ml.persistence import run_repository, spec_repository

        spec = spec_repository.get_latest_spec(session_id=session_id, db_path=db_path)
        if spec is None:
            spec_info = "Keine Pipeline konfiguriert"
            active_steps: list[str] = []
        else:
            spec_info = f"Version {spec['version']} ({spec['spec_id'][:8]}...)"
            active_steps = [
                s["type"]
                for s in spec["spec"].get("steps", [])
                if s.get("enabled", True)
            ]

        runs = run_repository.get_runs_for_session(session_id=session_id, db_path=db_path)
        run_count = len(runs)
        if runs:
            last_summary = runs[-1]
            last_status = last_summary["status"]
            # get_run() enthält result (geparst aus result_json), get_runs_for_session() nicht
            last_full = run_repository.get_run(last_summary["run_id"], db_path=db_path)
            metrics_str = "keine Metriken"
            if last_full:
                result = last_full.get("result") or {}
                metrics = result.get("metrics") or {}
                if metrics:
                    metrics_str = ", ".join(f"{k}: {v:.4f}" for k, v in metrics.items())
            last_run_info = f"Letzter Run: {last_status} ({metrics_str})"
        else:
            last_run_info = "Noch keine Runs ausgeführt"

        steps_str = ", ".join(active_steps) if active_steps else "keine"
        return (
            f"**Session-Status:**\n"
            f"- Spec: {spec_info}\n"
            f"- Runs: {run_count}\n"
            f"- {last_run_info}\n"
            f"- Aktive Steps: {steps_str}"
        )

    def _load_help_texts(self) -> dict:
        path = Path(__file__).parents[3] / "configs" / "help_texts.yaml"
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"help_texts.yaml nicht gefunden: {path}"
            ) from exc
