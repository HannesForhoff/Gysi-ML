import type { ResultResponse } from '../types'
import { sanitizeArtifactUrl } from '../utils/sanitizeArtifactUrl'
import { formatStepResult, getStepLabel } from '../utils/stepMeta'

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
