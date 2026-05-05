export interface ColumnStats {
  missing_count: number
  missing_pct: number
  distinct_count: number
  distinct_pct: number
  min?: number
  max?: number
  histogram?: {
    bins: number[]
    counts: number[]
  }
}

export interface DataApiResponse {
  columns: string[]
  rows: unknown[][]
  total_rows: number
  offset: number
  limit: number
  is_split: boolean
  column_stats?: Record<string, ColumnStats>
  train_rows?: number
  test_rows?: number
}

export async function fetchRunData(
  baseUrl: string,
  sessionId: string,
  runId: string,
  offset: number,
  limit: number,
  splitFilter: 'all' | 'train' | 'test' = 'all',
): Promise<DataApiResponse> {
  const base = baseUrl.replace(/\/+$/, '')
  const url = `${base}/v1/sessions/${encodeURIComponent(sessionId)}/runs/${encodeURIComponent(runId)}/data?offset=${offset}&limit=${limit}&split_filter=${splitFilter}`

  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`Datenabruf fehlgeschlagen (HTTP ${response.status})`)
  }

  const data: unknown = await response.json()
  return parseDataApiResponse(data)
}

export async function fetchRawData(
  baseUrl: string,
  sessionId: string,
  offset: number,
  limit: number,
): Promise<DataApiResponse> {
  const base = baseUrl.replace(/\/+$/, '')
  const url = `${base}/v1/sessions/${encodeURIComponent(sessionId)}/raw-data?offset=${offset}&limit=${limit}`

  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`Rohdaten-Abruf fehlgeschlagen (HTTP ${response.status})`)
  }

  const data: unknown = await response.json()
  return parseDataApiResponse(data)
}

function parseDataApiResponse(data: unknown): DataApiResponse {
  if (!isRecord(data)) {
    throw new Error('Daten-Response ist kein Objekt.')
  }

  if (!Array.isArray(data.columns)) {
    throw new Error('Daten-Response: columns fehlt oder ist kein Array.')
  }

  if (!Array.isArray(data.rows)) {
    throw new Error('Daten-Response: rows fehlt oder ist kein Array.')
  }

  if (typeof data.total_rows !== 'number') {
    throw new Error('Daten-Response: total_rows fehlt oder ist keine Zahl.')
  }

  const columns = data.columns.filter((c) => typeof c === 'string') as string[]
  const rows = data.rows.filter(Array.isArray) as unknown[][]
  const total_rows = data.total_rows
  const offset = typeof data.offset === 'number' ? data.offset : 0
  const limit = typeof data.limit === 'number' ? data.limit : 100
  const is_split = data.is_split === true
  const column_stats = isRecord(data.column_stats) ? parseColumnStats(data.column_stats) : undefined
  const train_rows = typeof data.train_rows === 'number' ? data.train_rows : undefined
  const test_rows = typeof data.test_rows === 'number' ? data.test_rows : undefined

  return { columns, rows, total_rows, offset, limit, is_split, column_stats, train_rows, test_rows }
}

function parseColumnStats(raw: Record<string, unknown>): Record<string, ColumnStats> {
  const result: Record<string, ColumnStats> = {}
  for (const [key, value] of Object.entries(raw)) {
    if (!isRecord(value)) continue
    result[key] = {
      missing_count: typeof value.missing_count === 'number' ? value.missing_count : 0,
      missing_pct: typeof value.missing_pct === 'number' ? value.missing_pct : 0,
      distinct_count: typeof value.distinct_count === 'number' ? value.distinct_count : 0,
      distinct_pct: typeof value.distinct_pct === 'number' ? value.distinct_pct : 0,
      min: typeof value.min === 'number' ? value.min : undefined,
      max: typeof value.max === 'number' ? value.max : undefined,
      histogram: parseHistogram(value.histogram),
    }
  }
  return result
}

function parseHistogram(raw: unknown): { bins: number[]; counts: number[] } | undefined {
  if (!isRecord(raw)) return undefined
  if (!Array.isArray(raw.bins) || !Array.isArray(raw.counts)) return undefined
  return {
    bins: raw.bins.filter((b) => typeof b === 'number') as number[],
    counts: raw.counts.filter((c) => typeof c === 'number') as number[],
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
