import type { StepResult } from '../types'

interface ChipRowProps {
  chips: string[]
  variant?: 'default' | 'removed' | 'added'
}

function ChipRow({ chips, variant = 'default' }: ChipRowProps) {
  const variantClass =
    variant === 'removed'
      ? ' stepDetailChip--removed'
      : variant === 'added'
        ? ' stepDetailChip--added'
        : ''
  return (
    <div className="stepDetailChips">
      {chips.map((chip, i) => (
        <span key={i} className={`stepDetailChip${variantClass}`}>
          {chip}
        </span>
      ))}
    </div>
  )
}

interface RowProps {
  label: string
  children: React.ReactNode
}

function Row({ label, children }: RowProps) {
  return (
    <div className="stepDetailRow">
      <span className="stepDetailRowLabel">{label}</span>
      <div className="stepDetailRowContent">{children}</div>
    </div>
  )
}

interface StepDetailProps {
  sr: StepResult
}

export function StepDetail({ sr }: StepDetailProps) {
  const m = sr.metadata

  switch (sr.step_type) {
    case 'dedup': {
      const n = Number(m.removed_duplicates ?? 0)
      return (
        <div className="stepDetail">
          <Row label="Ergebnis">
            <span className="stepDetailText">
              {n === 0 ? 'Keine Duplikate gefunden' : `${n} Duplikat(e) entfernt`}
            </span>
          </Row>
        </div>
      )
    }

    case 'impute_missing': {
      const perCol = m.imputed_values_per_column as Record<string, number> | undefined
      const warnings = m.warnings as string[] | undefined
      const strategy = m.strategy as string | undefined
      if (!perCol) return null
      const entries = Object.entries(perCol)
      const affected = entries.filter(([, n]) => n > 0)
      const clean = entries.filter(([, n]) => n === 0)
      return (
        <div className="stepDetail">
          {strategy && (
            <Row label="Strategie">
              <span className="stepDetailText">{strategy}</span>
            </Row>
          )}
          {affected.length > 0 ? (
            <Row label="Ersetzt">
              <ChipRow chips={affected.map(([col, n]) => `${col}: ${n}`)} variant="added" />
            </Row>
          ) : (
            <Row label="Ergebnis">
              <span className="stepDetailText">Keine fehlenden Werte</span>
            </Row>
          )}
          {clean.length > 0 && (
            <Row label="OK">
              <ChipRow chips={clean.map(([col]) => col)} />
            </Row>
          )}
          {warnings && warnings.length > 0 && (
            <Row label="Warnungen">
              <span className="stepDetailText">{warnings.join(' · ')}</span>
            </Row>
          )}
        </div>
      )
    }

    case 'split': {
      const train = Number(m.train_rows ?? 0)
      const test = Number(m.test_rows ?? 0)
      const total = train + test
      const testPct = total > 0 ? Math.round((test / total) * 100) : 0
      const trainPct = 100 - testPct
      const seed = m.random_state
      return (
        <div className="stepDetail">
          <div className="stepDetailSplit">
            <div className="stepDetailSplitBlock stepDetailSplitBlock--train">
              <span className="stepDetailSplitBlockLabel">Train</span>
              <span className="stepDetailSplitBlockVal">{train.toLocaleString('de-DE')}</span>
              <span className="stepDetailSplitBlockPct">{trainPct}%</span>
            </div>
            <div className="stepDetailSplitBlock stepDetailSplitBlock--test">
              <span className="stepDetailSplitBlockLabel">Test</span>
              <span className="stepDetailSplitBlockVal">{test.toLocaleString('de-DE')}</span>
              <span className="stepDetailSplitBlockPct">{testPct}%</span>
            </div>
          </div>
          {seed != null && (
            <Row label="Seed">
              <span className="stepDetailText">{String(seed)}</span>
            </Row>
          )}
        </div>
      )
    }

    case 'outlier_handling': {
      const treated = m.outliers_treated as Record<string, number> | undefined
      const bounds = m.bounds as
        | Record<string, { lower: number; upper: number; q1?: number; mean?: number }>
        | undefined
      const skipped = m.skipped_columns as Record<string, string> | undefined
      const method = m.method as string | undefined
      const zThreshold = m.zscore_threshold as number | undefined
      if (!treated) return null
      const entries = Object.entries(treated)
      return (
        <div className="stepDetail">
          {method && (
            <Row label="Methode">
              <span className="stepDetailText">
                {method === 'iqr' ? 'IQR (Winsorization)' : method === 'zscore' ? `Z-Score (k = ${zThreshold ?? 3})` : method}
              </span>
            </Row>
          )}
          {entries.length > 0 && (
            <Row label="Spalten">
              <div className="stepDetailOutlierTable">
                {entries.map(([col, n]) => {
                  const b = bounds?.[col]
                  return (
                    <div key={col} className="stepDetailOutlierRow">
                      <span className="stepDetailOutlierCol">{col}</span>
                      <span
                        className={`stepDetailOutlierCount${n > 0 ? ' stepDetailOutlierCount--positive' : ''}`}
                      >
                        {n > 0 ? `${n}×` : '✓'}
                      </span>
                      {b && (
                        <span className="stepDetailOutlierBounds">
                          [{b.lower} – {b.upper}]
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
            </Row>
          )}
          {skipped && Object.keys(skipped).length > 0 && (
            <Row label="Übersprungen">
              <ChipRow chips={Object.keys(skipped)} />
            </Row>
          )}
        </div>
      )
    }

    case 'encode_categorical': {
      const cols = m.encoded_columns as string[] | undefined
      const warnings = m.warnings as string[] | undefined
      const method = m.method as string | undefined
      if (!cols || cols.length === 0) {
        return (
          <div className="stepDetail">
            <Row label="Ergebnis">
              <span className="stepDetailText">Keine kategorischen Spalten</span>
            </Row>
          </div>
        )
      }
      return (
        <div className="stepDetail">
          {method && (
            <Row label="Methode">
              <span className="stepDetailText">{method === 'label' ? 'Label Encoding' : method === 'onehot' ? 'One-Hot Encoding' : method}</span>
            </Row>
          )}
          <Row label="Kodiert">
            <ChipRow chips={cols} />
          </Row>
          {warnings && warnings.length > 0 && (
            <Row label="Warnungen">
              <span className="stepDetailText">{warnings.join(' · ')}</span>
            </Row>
          )}
        </div>
      )
    }

    case 'correlation_filter': {
      const dropped = m.dropped_features as string[] | undefined
      const pairs = m.corr_pairs as
        | Array<{ col_a: string; col_b: string; value: number; dropped: string }>
        | undefined
      const independent = m.independent_features as string[] | undefined
      const threshold = m.threshold as number | undefined
      return (
        <div className="stepDetail">
          {threshold != null && (
            <Row label="Schwellwert">
              <span className="stepDetailText">|r| ≥ {threshold}</span>
            </Row>
          )}
          {pairs && pairs.length > 0 && (
            <Row label="Paare">
              <div className="stepDetailCorrPairs">
                {pairs.map((p, i) => (
                  <div key={i} className="stepDetailCorrPair">
                    <span>{p.col_a}</span>
                    <span className="stepDetailCorrOp">↔</span>
                    <span>{p.col_b}</span>
                    <span className="stepDetailCorrVal">r={p.value.toFixed(2)}</span>
                    <span className="stepDetailCorrDropped">→ {p.dropped} entfernt</span>
                  </div>
                ))}
              </div>
            </Row>
          )}
          {dropped && dropped.length > 0 ? (
            <Row label="Entfernt">
              <ChipRow chips={dropped} variant="removed" />
            </Row>
          ) : (
            <Row label="Ergebnis">
              <span className="stepDetailText">Keine hochkorrelierten Features</span>
            </Row>
          )}
          {independent && independent.length > 0 && (
            <Row label="Behalten">
              <ChipRow chips={independent} variant="added" />
            </Row>
          )}
        </div>
      )
    }

    case 'rare_category_bucketing': {
      const perCol = m.rare_categories_per_column as Record<string, number> | undefined
      const minFreq = m.min_frequency as number | undefined
      if (!perCol) return null
      const entries = Object.entries(perCol)
      const found = entries.filter(([, n]) => n > 0)
      return (
        <div className="stepDetail">
          {minFreq != null && (
            <Row label="Schwellwert">
              <span className="stepDetailText">&lt; {(minFreq * 100).toFixed(1)}%</span>
            </Row>
          )}
          {found.length > 0 ? (
            <Row label="Gebündelt">
              <ChipRow chips={found.map(([col, n]) => `${col}: ${n}`)} />
            </Row>
          ) : (
            <Row label="Ergebnis">
              <span className="stepDetailText">Keine seltenen Kategorien gefunden</span>
            </Row>
          )}
        </div>
      )
    }

    case 'time_feature_encoding': {
      const derived = m.derived_features as string[] | undefined
      const dropped = m.dropped_column as string | undefined
      return (
        <div className="stepDetail">
          {derived && derived.length > 0 && (
            <Row label="Abgeleitet">
              <ChipRow chips={derived} variant="added" />
            </Row>
          )}
          {dropped && (
            <Row label="Entfernt">
              <ChipRow chips={[dropped]} variant="removed" />
            </Row>
          )}
        </div>
      )
    }

    case 'cast_dtype': {
      const casts = m.casts_applied as
        | Record<string, { old_dtype: string; new_dtype: string }>
        | undefined
      if (!casts) return null
      const entries = Object.entries(casts)
      if (entries.length === 0) {
        return (
          <div className="stepDetail">
            <Row label="Ergebnis">
              <span className="stepDetailText">Keine Konvertierungen durchgeführt</span>
            </Row>
          </div>
        )
      }
      return (
        <div className="stepDetail">
          <Row label="Konvertiert">
            <div className="stepDetailDtypeTable">
              {entries.map(([col, { old_dtype, new_dtype }]) => (
                <div key={col} className="stepDetailDtypeRow">
                  <span className="stepDetailDtypeCol">{col}</span>
                  <span className="stepDetailDtypeOld">{old_dtype}</span>
                  <span className="stepDetailDtypeArrow">→</span>
                  <span className="stepDetailDtypeNew">{new_dtype}</span>
                </div>
              ))}
            </div>
          </Row>
        </div>
      )
    }

    case 'train_decision_tree':
    case 'train_ebm': {
      const features = m.feature_names as string[] | undefined
      const metrics = m.metrics as Record<string, number> | undefined
      const target = m.target as string | undefined
      const maxDepth = m.max_depth as number | null | undefined
      return (
        <div className="stepDetail">
          {target && (
            <Row label="Zielgröße">
              <span className="stepDetailChip stepDetailChip--added">{target}</span>
            </Row>
          )}
          {sr.step_type === 'train_decision_tree' && (
            <Row label="Max. Tiefe">
              <span className="stepDetailText">{maxDepth != null ? String(maxDepth) : 'unbegrenzt'}</span>
            </Row>
          )}
          {metrics && (
            <Row label="Metriken">
              <div className="stepDetailMetrics">
                {metrics.rmse != null && (
                  <div className="stepDetailMetric">
                    <span className="stepDetailMetricVal">{metrics.rmse.toFixed(1)}</span>
                    <span className="stepDetailMetricLabel">RMSE</span>
                  </div>
                )}
                {metrics.mae != null && (
                  <div className="stepDetailMetric">
                    <span className="stepDetailMetricVal">{metrics.mae.toFixed(1)}</span>
                    <span className="stepDetailMetricLabel">MAE</span>
                  </div>
                )}
                {metrics.r2 != null && (
                  <div className="stepDetailMetric">
                    <span className="stepDetailMetricVal">{metrics.r2.toFixed(3)}</span>
                    <span className="stepDetailMetricLabel">R²</span>
                  </div>
                )}
              </div>
            </Row>
          )}
          {features && features.length > 0 && (
            <Row label={`Features (${features.length})`}>
              <ChipRow chips={features} />
            </Row>
          )}
        </div>
      )
    }

    case 'catboost_feature_selection': {
      const selected = m.selected_features as string[] | undefined
      const removed = m.removed_features as string[] | undefined
      return (
        <div className="stepDetail">
          {selected && selected.length > 0 && (
            <Row label={`Ausgewählt (${selected.length})`}>
              <ChipRow chips={selected} variant="added" />
            </Row>
          )}
          {removed && removed.length > 0 && (
            <Row label={`Entfernt (${removed.length})`}>
              <ChipRow chips={removed} variant="removed" />
            </Row>
          )}
        </div>
      )
    }

    default:
      return null
  }
}
