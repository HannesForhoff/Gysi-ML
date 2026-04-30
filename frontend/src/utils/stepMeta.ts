import type { StepResult } from '../types'

export const STEP_LABELS: Record<string, string> = {
  dedup: 'Duplikate entfernen',
  impute_missing: 'Fehlende Werte auffüllen',
  split: 'Train/Test-Aufteilung',
  outlier_handling: 'Ausreißer behandeln',
  encode_categorical: 'Kategorien kodieren',
  correlation_filter: 'Korrelationsfilter',
  rare_category_bucketing: 'Seltene Kategorien bündeln',
  time_feature_encoding: 'Zeitmerkmale ableiten',
  cast_dtype: 'Datentypen anpassen',
  plot_distribution: 'Verteilungsplot',
  train_decision_tree: 'Decision Tree trainiert',
  train_ebm: 'EBM trainiert',
  catboost_feature_selection: 'CatBoost Feature Selection',
  train_model: 'Modell trainieren',
  evaluate_model: 'Modell auswerten',
}

export function getStepLabel(stepType: string): string {
  return STEP_LABELS[stepType] ?? stepType
}

export function formatStepResult(sr: StepResult): string {
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
      const cols = m.encoded_columns as string[] | undefined
      if (Array.isArray(cols) && cols.length > 0) {
        return `Kodiert: ${cols.join(', ')}`
      }
      const warnings = m.warnings as string[] | undefined
      if (warnings && warnings.length > 0) {
        return `Übersprungen: ${warnings.join(' ')}`
      }
      return 'Übersprungen – keine kategorialen Spalten gefunden.'
    }
    case 'correlation_filter': {
      const dropped = m.dropped_features as string[] | undefined
      const threshold = m.threshold as number | undefined
      const analysisOnly = m.analysis_only as boolean | undefined
      const pairs = m.corr_pairs as
        | Array<{ col_a: string; col_b: string; value: number; dropped: string }>
        | undefined

      const thr = threshold != null ? threshold : 0.9
      const pairCount = pairs?.length ?? 0

      if (analysisOnly) {
        if (pairCount === 0) {
          return `Keine hochkorrelierten Features gefunden (|r| < ${thr})`
        }
        return `${pairCount} korrelierte Paar${pairCount === 1 ? '' : 'e'} gefunden (|r| ≥ ${thr}) — noch keine Features entfernt`
      }

      // Drop-Modus (User hat Entscheidung getroffen)
      if (dropped && dropped.length > 0) {
        return `${dropped.length} Feature${dropped.length === 1 ? '' : 's'} entfernt: ${dropped.join(', ')}`
      }
      return 'Keine Features entfernt.'
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
    case 'train_decision_tree': {
      const features = m.feature_names as string[] | undefined
      if (features && features.length > 0) {
        return `${features.length} Features`
      }
      return 'Modell trainiert.'
    }
    case 'train_ebm': {
      const features = m.feature_names as string[] | undefined
      if (features && features.length > 0) {
        return `${features.length} Features`
      }
      return 'Modell trainiert.'
    }
    case 'catboost_feature_selection': {
      const analysisOnly = m.analysis_only as boolean | undefined
      const selected = m.selected_features as string[] | undefined
      const removed = m.removed_features as string[] | undefined
      if (analysisOnly) {
        const total = (selected?.length ?? 0) + (removed?.length ?? 0)
        return `Analyse abgeschlossen — ${total} Features bewertet, noch keine Entfernung`
      }
      const parts: string[] = []
      if (selected && selected.length > 0) parts.push(`${selected.length} ausgewählt`)
      if (removed && removed.length > 0) parts.push(`entfernt: ${removed.join(', ')}`)
      return parts.length > 0 ? parts.join(' — ') : 'Feature Selection abgeschlossen.'
    }
    case 'cast_dtype': {
      const casts = m.casts_applied as
        | Record<string, { old_dtype: string; new_dtype: string }>
        | undefined
      if (casts && typeof casts === 'object') {
        const entries = Object.entries(casts)
        if (entries.length === 0) return 'Keine Konvertierungen durchgeführt.'
        return entries
          .map(([col, { old_dtype, new_dtype }]) => `${col}: ${old_dtype} → ${new_dtype}`)
          .join(', ')
      }
      return 'Datentypen angepasst.'
    }
    case 'plot_distribution': {
      const feature = m.feature as string | undefined
      const groupBy = m.group_by as string | undefined
      const n = m.n_values as number | undefined
      const mean = m.mean as number | undefined
      const parts: string[] = []
      if (feature) parts.push(groupBy ? `${feature} nach ${groupBy}` : feature)
      if (n != null) parts.push(`n=${n}`)
      if (mean != null && !groupBy) parts.push(`Ø ${mean}`)
      return parts.length > 0 ? parts.join(' — ') : 'Plot erstellt.'
    }
    default:
      return ''
  }
}

/**
 * Gibt true zurück wenn ein Step zwar ausgeführt wurde, aber
 * nichts am Datensatz verändert hat (= übersprungen / ohne Wirkung).
 * Wird in ResultCard genutzt um das Icon auf ⚠ zu wechseln.
 */
export function isStepSkipped(sr: StepResult): boolean {
  const m = sr.metadata
  if (sr.step_type === 'encode_categorical') {
    const cols = m.encoded_columns as string[] | undefined
    return Array.isArray(cols) && cols.length === 0
  }
  return false
}