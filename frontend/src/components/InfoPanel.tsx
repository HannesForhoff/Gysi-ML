import type { ArtifactRef, ResultResponse, SpecSummary, StepResult } from '../types'
import { sanitizeArtifactUrl } from '../utils/sanitizeArtifactUrl'
import { getStepLabel } from '../utils/stepMeta'
import { StepDetail } from './StepDetail'

type InfoPanelProps = {
  specSummary: SpecSummary | null
  lastRun: ResultResponse | null
  artifacts: ArtifactRef[]
}

function mediaTypeShort(mt: string): string {
  if (mt === 'text/csv') return 'CSV'
  if (mt === 'application/json') return 'JSON'
  if (mt.startsWith('image/')) return mt.split('/')[1]?.toUpperCase() ?? 'IMG'
  const slash = mt.lastIndexOf('/')
  return slash >= 0 ? mt.slice(slash + 1).toUpperCase() : mt.toUpperCase()
}

export function InfoPanel({ specSummary, lastRun, artifacts }: InfoPanelProps) {
  const runDone = lastRun?.status === 'done'
  const hasSteps = (lastRun?.step_results?.length ?? 0) > 0
  const hasArtifacts = artifacts.length > 0

  // step_results are in the same order as spec steps — match by index
  const stepResults: (StepResult | undefined)[] = lastRun?.step_results ?? []

  return (
    <div className="infoPanel">

      {/* ── Aktive Pipeline ── */}
      <div className="infoBlock">
        <div className="infoBlockHeader">
          <span className="infoBlockTitle">Aktive Pipeline</span>
          {specSummary && (
            <span className="infoVersionBadge">
              {specSummary.spec_version_id.length > 12
                ? specSummary.spec_version_id.slice(0, 8) + '…'
                : specSummary.spec_version_id}
            </span>
          )}
        </div>
        {specSummary ? (
          <ul className="infoPipelineSteps">
            {specSummary.steps.map((step, idx) => {
              const sr = stepResults[idx]
              return (
                <li key={`${step.step_type}-${idx}`} className="infoPipelineStep">
                  <div className="infoPipelineStepHeader">
                    <span className="infoPipelineStepNum">{idx + 1}</span>
                    <span className="infoPipelineStepName">{getStepLabel(step.step_type)}</span>
                    <span
                      className={`infoStepBadge ${step.enabled ? 'infoStepBadge--on' : 'infoStepBadge--off'}`}
                    >
                      {step.enabled ? 'aktiv' : 'aus'}
                    </span>
                  </div>
                  {sr && step.enabled && (
                    <div className="infoPipelineStepDetail">
                      <StepDetail sr={sr} />
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        ) : (
          <div className="infoEmpty">Noch keine Pipeline konfiguriert.</div>
        )}
      </div>

      {/* ── Letzter Run ── */}
      <div className="infoBlock">
        <div className="infoBlockHeader">
          <span className="infoBlockTitle">Letzter Run</span>
          {lastRun && (
            <span
              className={`infoRunStatusChip ${
                runDone ? 'infoRunStatusChip--done' : 'infoRunStatusChip--failed'
              }`}
            >
              {runDone ? '● Erfolg' : '✗ Fehler'}
            </span>
          )}
        </div>
        {hasSteps ? (
          <ul className="infoRunStepList">
            {lastRun!.step_results!.map((sr, idx) => (
              <li key={idx} className="infoRunStep">
                <span className="infoRunStepIcon">✓</span>
                <div className="infoRunStepContent">
                  <span className="infoRunStepName">{getStepLabel(sr.step_type)}</span>
                  <StepDetail sr={sr} />
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="infoEmpty">Noch kein Run ausgeführt.</div>
        )}
      </div>

      {/* ── Artefakte ── */}
      <div className="infoBlock">
        <div className="infoBlockHeader">
          <span className="infoBlockTitle">Artefakte</span>
          {hasArtifacts && (
            <span className="infoArtifactCount">{artifacts.length}</span>
          )}
        </div>
        {hasArtifacts ? (
          <ul className="infoArtifactList">
            {artifacts.map((artifact) => {
              const safeUrl = sanitizeArtifactUrl(artifact.url)
              const isImage = artifact.media_type?.startsWith('image/')
              return (
                <li key={artifact.id} className="infoArtifactItem">
                  <div className="infoArtifactMain">
                    <span className="infoArtifactIcon">{isImage ? '🖼' : '📎'}</span>
                    <span className="infoArtifactLabel">{artifact.label}</span>
                  </div>
                  <span className="infoArtifactType">{mediaTypeShort(artifact.media_type)}</span>
                  {safeUrl ? (
                    <a
                      href={safeUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="infoArtifactDownload"
                    >
                      ↓
                    </a>
                  ) : null}
                </li>
              )
            })}
          </ul>
        ) : (
          <div className="infoEmpty">Keine Artefakte erzeugt.</div>
        )}
      </div>
    </div>
  )
}
