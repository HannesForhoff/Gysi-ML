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
