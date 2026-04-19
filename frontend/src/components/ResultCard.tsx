import type { ResultResponse, StepResult } from '../types'
import { sanitizeArtifactUrl } from '../utils/sanitizeArtifactUrl'

type ResultCardProps = {
  result: ResultResponse
}

function formatStepResult(sr: StepResult): string {
  const m = sr.metadata
  switch (sr.step_type) {
    case 'dedup': {
      const n = Number(m.removed_duplicates ?? 0)
      return n === 0 ? 'Keine Duplikate gefunden.' : `${n} Duplikat(e) entfernt.`
    }
    case 'impute_missing': {
      const perCol = m.imputed_values_per_column
      if (perCol && typeof perCol === 'object') {
        const entries = Object.entries(perCol as Record<string, number>)
        if (entries.length === 0) return 'Keine fehlenden Werte gefunden.'
        return entries.map(([col, n]) => `${col}: ${n} Wert(e) ersetzt`).join(', ')
      }
      return 'Imputation abgeschlossen.'
    }
    case 'split': {
      const train = m.train_rows
      const test = m.test_rows
      const size = m.test_size
      if (train != null && test != null) {
        const pct = size != null ? ` (${Math.round(Number(size) * 100)}% Test)` : ''
        return `${train} Train-Zeilen / ${test} Test-Zeilen${pct}`
      }
      return 'Split abgeschlossen.'
    }
    case 'outlier_handling': {
      const treated = m.outliers_treated
      if (treated && typeof treated === 'object') {
        const bounds = m.bounds as Record<string, { lower: number; upper: number }> | undefined
        const skipped = m.skipped_columns as Record<string, string> | undefined
        const entries = Object.entries(treated as Record<string, number>).filter(([, n]) => n > 0)
        const parts: string[] = []
        if (entries.length > 0) {
          parts.push(
            entries
              .map(([col, n]) => {
                const b = bounds?.[col]
                const boundsStr = b != null ? ` [${b.lower} – ${b.upper}]` : ''
                return `${col}: ${n} Ausreißer${boundsStr}`
              })
              .join(', '),
          )
        }
        if (skipped && Object.keys(skipped).length > 0) {
          parts.push(`Übersprungen (IQR=0): ${Object.keys(skipped).join(', ')}`)
        }
        if (parts.length === 0) return 'Keine Ausreißer gefunden.'
        return parts.join(' | ')
      }
      return 'Ausreißer-Behandlung abgeschlossen.'
    }
    case 'encode_categorical': {
      const cols = m.encoded_columns
      if (Array.isArray(cols) && cols.length > 0) {
        return `Kodiert: ${(cols as string[]).join(', ')}`
      }
      return 'Encoding abgeschlossen.'
    }
    case 'correlation_filter': {
      const dropped = m.dropped_features as string[] | undefined
      const pairs = m.corr_pairs as
        | Array<{ col_a: string; col_b: string; value: number; dropped: string }>
        | undefined
      const independent = m.independent_features as string[] | undefined

      const parts: string[] = []

      if (pairs && pairs.length > 0) {
        const pairStr = pairs
          .map((p) => `${p.col_a}↔${p.col_b} (r=${p.value}, entfernt: ${p.dropped})`)
          .join(' | ')
        parts.push(`Korrelierte Paare: ${pairStr}`)
      }

      if (dropped && dropped.length > 0) {
        parts.push(`Entfernt: ${dropped.join(', ')}`)
      } else {
        parts.push('Keine hochkorrelierten Features gefunden.')
      }

      if (independent && independent.length > 0) {
        parts.push(`Eigenständig: ${independent.join(', ')}`)
      }

      return parts.join(' — ')
    }
    case 'rare_category_bucketing': {
      const perCol = m.rare_categories_per_column
      if (perCol && typeof perCol === 'object') {
        const entries = Object.entries(perCol as Record<string, number>)
        const found = entries.filter(([, n]) => n > 0)
        if (found.length === 0) {
          return 'Keine seltenen Kategorien gefunden. Erhöhe min_frequency, um mehr Werte als selten einzustufen.'
        }
        return found.map(([col, n]) => `${col}: ${n} Kategorie(n) gebündelt`).join(', ')
      }
      return 'Rare-Category-Bucketing abgeschlossen.'
    }
    case 'time_feature_encoding': {
      const derived = m.derived_features as string[] | undefined
      const dropped = m.dropped_column as string | undefined
      const parts: string[] = []
      if (derived && derived.length > 0) {
        parts.push(`Abgeleitet: ${derived.join(', ')}`)
      }
      if (dropped) {
        parts.push(`${dropped} entfernt`)
      }
      return parts.length > 0 ? parts.join(' | ') : 'Zeit-Feature-Encoding abgeschlossen.'
    }
    default:
      return JSON.stringify(m)
  }
}

export function ResultCard({ result }: ResultCardProps) {
  const isDone = result.status === 'done'
  const statusLabel = isDone ? 'Ergebnis' : 'Fehlgeschlagen'
  const modifier = isDone ? 'resultCard--done' : 'resultCard--failed'

  const hasMetrics =
    result.metrics != null && Object.keys(result.metrics).length > 0

  const hasArtifacts =
    result.artifacts != null && result.artifacts.length > 0

  const hasStepResults =
    result.step_results != null && result.step_results.length > 0

  return (
    <div className={`resultCard ${modifier}`}>
      <div className="resultLabel">{statusLabel}</div>

      {result.message && (
        <div className="resultMessage">{result.message}</div>
      )}

      {hasStepResults && (
        <ul className="resultStepResults">
          {result.step_results!.map((sr, idx) => (
            <li key={idx} className="resultStepResult">
              <span className="resultStepIcon">✓</span>
              <span className="resultStepType">{sr.step_type}</span>
              <span className="resultStepDetail">{formatStepResult(sr)}</span>
            </li>
          ))}
        </ul>
      )}

      {hasMetrics && (
        <dl className="resultMetrics">
          {Object.entries(result.metrics!).map(([key, value]) => (
            <div key={key} className="resultMetricsRow">
              <dt>{key}</dt>
              <dd>{String(value)}</dd>
            </div>
          ))}
        </dl>
      )}

      {hasArtifacts && (
        <ul className="resultArtifacts">
          {result.artifacts!.map((artifact) => {
            const safeUrl = sanitizeArtifactUrl(artifact.url)
            const isImage = artifact.media_type?.startsWith('image/')

            return (
              <li key={artifact.id}>
                {safeUrl ? (
                  isImage ? (
                    <figure className="resultArtifactFigure">
                      <img
                        src={safeUrl}
                        alt={artifact.label}
                        className="resultArtifactImage"
                      />
                      <figcaption className="resultArtifactCaption">
                        {artifact.label}
                        <a
                          href={safeUrl}
                          download
                          target="_blank"
                          rel="noreferrer"
                          className="resultArtifactDownload"
                        >
                          ↓ Download
                        </a>
                      </figcaption>
                    </figure>
                  ) : (
                    <a
                      href={safeUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="resultArtifactLink"
                    >
                      {artifact.label}
                      {artifact.media_type && (
                        <span className="resultArtifactType"> ({artifact.media_type})</span>
                      )}
                    </a>
                  )
                ) : (
                  <span className="resultArtifactInvalid">
                    {artifact.label} (ungültige URL)
                    {artifact.media_type && (
                      <span className="resultArtifactType"> ({artifact.media_type})</span>
                    )}
                  </span>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
