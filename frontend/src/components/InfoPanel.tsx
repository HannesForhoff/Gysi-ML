import { useMemo } from 'react'

import type { ArtifactRef, ResultResponse, SpecSummary, StepResult } from '../types'
import { sanitizeArtifactUrl } from '../utils/sanitizeArtifactUrl'
import { getStepLabel } from '../utils/stepMeta'
import { StepDetail } from './StepDetail'

type InfoPanelProps = {
  specSummary: SpecSummary | null
  lastRun: ResultResponse | null
  artifacts: ArtifactRef[]
  versionMetrics: Record<string, Record<string, number | string>>
}

function mediaTypeShort(mt: string): string {
  if (mt === 'text/csv') return 'CSV'
  if (mt === 'application/json') return 'JSON'
  if (mt.startsWith('image/')) return mt.split('/')[1]?.toUpperCase() ?? 'IMG'
  const slash = mt.lastIndexOf('/')
  return slash >= 0 ? mt.slice(slash + 1).toUpperCase() : mt.toUpperCase()
}

export function InfoPanel({ specSummary, lastRun, artifacts, versionMetrics }: InfoPanelProps) {
  const runDone = lastRun?.status === 'done'
  const hasSteps = (lastRun?.step_results?.length ?? 0) > 0
  const hasArtifacts = artifacts.length > 0

  // step_results werden per step_type gematcht, nicht per Index (Bug 1.13 Fix C)
  const stepResults: StepResult[] = lastRun?.step_results ?? []

  // Nth-Occurrence-Matching: mehrere Steps desselben Typs (z.B. zwei impute_missing mit
  // verschiedenen Strategien) erhalten jeweils die korrekte step_result, nicht immer die erste.
  const specStepResults = useMemo(() => {
    const countSeen: Record<string, number> = {}
    return (specSummary?.steps ?? []).map(step => {
      const seenBefore = countSeen[step.step_type] ?? 0
      countSeen[step.step_type] = seenBefore + 1
      let matchCount = 0
      return stepResults.find(r => {
        if (r.step_type === step.step_type) {
          if (matchCount === seenBefore) return true
          matchCount++
        }
        return false
      }) ?? null
    })
  }, [specSummary, stepResults])

  // Artefakte nach Spec-Version gruppieren (neueste zuerst)
  const artifactGroups = useMemo(() => {
    const map = new Map<string, ArtifactRef[]>()
    for (const a of artifacts) {
      const key = a.spec_version ?? '—'
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(a)
    }
    // Sortierung: vN numerisch absteigend, unbekannte ans Ende
    return [...map.entries()].sort(([a], [b]) => {
      if (a === '—') return 1
      if (b === '—') return -1
      const numA = parseInt(a.replace(/\D/g, ''), 10)
      const numB = parseInt(b.replace(/\D/g, ''), 10)
      return isNaN(numA) || isNaN(numB) ? b.localeCompare(a) : numB - numA
    })
  }, [artifacts])

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
              const sr = specStepResults[idx]
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
          <div className="infoArtifactGroups">
            {artifactGroups.map(([version, items]) => (
              <div key={version} className="infoArtifactGroup">
                <div className="infoArtifactGroupHeader">
                  <span className="infoArtifactGroupVersion">{version}</span>
                  <span className="infoArtifactGroupCount">{items.length}</span>
                </div>
                {versionMetrics[version] && Object.keys(versionMetrics[version]).length > 0 && (
                  <div className="infoVersionMetrics">
                    {Object.entries(versionMetrics[version]).map(([k, v]) => (
                      <span key={k} className="infoVersionMetricChip">
                        <span className="infoVersionMetricLabel">{k.toUpperCase()}</span>
                        <span className="infoVersionMetricVal">
                          {typeof v === 'number'
                            ? k === 'r2' ? v.toFixed(4) : v.toFixed(3)
                            : String(v)}
                        </span>
                      </span>
                    ))}
                  </div>
                )}
                <ul className="infoArtifactList">
                  {items.map((artifact) => {
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
              </div>
            ))}
          </div>
        ) : (
          <div className="infoEmpty">Keine Artefakte erzeugt.</div>
        )}
      </div>
    </div>
  )
}
