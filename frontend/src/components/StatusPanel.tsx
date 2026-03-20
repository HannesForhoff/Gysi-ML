import type { ArtifactRef, ResultResponse, SpecSummary } from '../types'
import type { TransportInfo, UiState } from '../state/chatReducer'
import { sanitizeArtifactUrl } from '../utils/sanitizeArtifactUrl'

type StatusPanelProps = {
  transport: TransportInfo
  ui: UiState
  specSummary: SpecSummary | null
  lastRun: ResultResponse | null
  artifacts: ArtifactRef[]
  lastError: string | null
  isLongRunning: boolean
}

function uiLabel(ui: UiState): string {
  switch (ui.type) {
    case 'idle':
      return 'Bereit'
    case 'sending_message':
      return 'Sendet…'
    case 'proposal_pending':
      return 'Vorschlag ausstehend'
    case 'run_polling':
      return 'Run läuft…'
    case 'run_done':
      return 'Run abgeschlossen'
    case 'run_failed':
      return 'Run fehlgeschlagen'
    case 'validation_error':
      return 'Validierungsfehler'
    case 'backend_unreachable':
      return 'Backend nicht erreichbar'
  }
}

export function StatusPanel({
  transport,
  ui,
  specSummary,
  lastRun,
  artifacts,
  lastError,
  isLongRunning,
}: StatusPanelProps) {
  return (
    <div>
      {ui.type === 'backend_unreachable' && (
        <div className="statusBlock statusBlock--error">
          <div className="statusTitle">Verbindungsfehler</div>
          <div className="statusMeta">
            Backend nicht erreichbar. Bitte Backend starten oder URL prüfen.
          </div>
        </div>
      )}

      {ui.type === 'validation_error' && (
        <div className="statusBlock statusBlock--warning">
          <div className="statusTitle">Hinweis</div>
          <div className="statusMeta">
            Validierungsfehler aufgetreten. Sieh dir die Fehlermeldung im Chat an
            und sende eine neue Nachricht.
          </div>
        </div>
      )}

      {isLongRunning && ui.type === 'run_polling' && (
        <div className="statusBlock statusBlock--info">
          <div className="statusTitle">Hinweis</div>
          <div className="statusMeta">
            Run dauert länger – wir aktualisieren weiter.
          </div>
        </div>
      )}

      <div className="statusBlock">
        <div className="statusTitle">Backend</div>
        <div className="statusMeta">
          {transport.useMock ? 'Mock aktiv' : 'Mock aus'}
        </div>
        {!transport.useMock ? (
          <div className="statusMeta">Base URL: {transport.backendBaseUrl}</div>
        ) : null}
        <div className="statusMeta">UI State: {uiLabel(ui)}</div>
        {lastError ? <div className="statusMeta">Error: {lastError}</div> : null}
      </div>

      <div className="statusBlock">
        <div className="statusTitle">Spec Summary</div>
        {specSummary ? (
          <>
            <div className="statusMeta">Version: {specSummary.spec_version_id}</div>
            <ul className="statusList">
              {specSummary.steps.map((step) => (
                <li key={step.step_type}>
                  <span className="statusMeta">
                    {step.step_type} — {step.enabled ? 'enabled' : 'disabled'}
                  </span>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <div className="statusMeta">(noch keine Daten)</div>
        )}
      </div>

      <div className="statusBlock">
        <div className="statusTitle">Letzter Run</div>
        {lastRun ? (
          <>
            <div className="statusMeta">Status: {lastRun.status}</div>
            {lastRun.metrics ? (
              <div className="statusMeta">
                Metrics: {Object.entries(lastRun.metrics).length}
              </div>
            ) : null}
          </>
        ) : (
          <div className="statusMeta">(noch kein Run)</div>
        )}
      </div>

      <div className="statusBlock">
        <div className="statusTitle">Artefakte</div>
        {artifacts.length > 0 ? (
          <ul className="statusList">
            {artifacts.map((artifact) => {
              const safeUrl = sanitizeArtifactUrl(artifact.url)

              return (
                <li key={artifact.id}>
                  {safeUrl ? (
                    <a href={safeUrl} target="_blank" rel="noreferrer">
                      {artifact.label}
                    </a>
                  ) : (
                    <span className="statusMeta">{artifact.label} (ungültige URL)</span>
                  )}
                  <div className="statusMeta">{artifact.media_type}</div>
                </li>
              )
            })}
          </ul>
        ) : (
          <div className="statusMeta">(keine)</div>
        )}
      </div>
    </div>
  )
}
