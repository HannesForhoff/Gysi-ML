import type { ResultResponse } from '../types'
import { sanitizeArtifactUrl } from '../utils/sanitizeArtifactUrl'

type ResultCardProps = {
  result: ResultResponse
}

export function ResultCard({ result }: ResultCardProps) {
  const isDone = result.status === 'done'
  const statusLabel = isDone ? 'Ergebnis' : 'Fehlgeschlagen'
  const modifier = isDone ? 'resultCard--done' : 'resultCard--failed'

  const hasMetrics =
    result.metrics != null && Object.keys(result.metrics).length > 0

  const hasArtifacts =
    result.artifacts != null && result.artifacts.length > 0

  return (
    <div className={`resultCard ${modifier}`}>
      <div className="resultLabel">{statusLabel}</div>

      {result.message && (
        <div className="resultMessage">{result.message}</div>
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

            return (
              <li key={artifact.id}>
                {safeUrl ? (
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
