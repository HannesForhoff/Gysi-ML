import type { ResultResponse } from '../types'
import { sanitizeArtifactUrl } from '../utils/sanitizeArtifactUrl'
import { formatStepResult, getStepLabel } from '../utils/stepMeta'

type ResultCardProps = {
  result: ResultResponse
}

const METRIC_LABELS: Record<string, string> = {
  rmse: 'RMSE',
  mae: 'MAE',
  r2: 'R²',
  mse: 'MSE',
  accuracy: 'Accuracy',
}

function formatMetricValue(key: string, value: number | string): string {
  if (typeof value === 'number') {
    // R² auf 4 Stellen, Rest auf 2
    return key === 'r2' ? value.toFixed(4) : value.toFixed(2)
  }
  return String(value)
}

function mediaTypeLabel(mediaType: string): string {
  if (mediaType === 'text/csv') return 'CSV'
  if (mediaType.startsWith('image/')) return mediaType.split('/')[1]?.toUpperCase() ?? 'IMG'
  const slash = mediaType.lastIndexOf('/')
  return slash >= 0 ? mediaType.slice(slash + 1).toUpperCase() : mediaType.toUpperCase()
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
              <div className="resultStepContent">
                <span className="resultStepType">{getStepLabel(sr.step_type)}</span>
                <span className="resultStepDetail">{formatStepResult(sr)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}

      {hasMetrics && (
        <div className="resultMetricsBox">
          <div className="resultMetricsBoxTitle">Modell-Ergebnisse</div>
          <dl className="resultMetrics">
            {Object.entries(result.metrics!).map(([key, value]) => (
              <div key={key} className="resultMetricsRow">
                <dt>{METRIC_LABELS[key] ?? key.toUpperCase()}</dt>
                <dd>{formatMetricValue(key, value as number | string)}</dd>
              </div>
            ))}
          </dl>
        </div>
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
                      <span className="resultArtifactFileIcon">📄</span>
                      {artifact.label}
                      <span className="resultArtifactTypeBadge">{mediaTypeLabel(artifact.media_type)}</span>
                    </a>
                  )
                ) : (
                  <span className="resultArtifactInvalid">
                    {artifact.label} (ungültige URL)
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
