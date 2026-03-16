export interface FrontendEnv {
  backendBaseUrl: string
  useMock: boolean
}

function readEnvValue(name: string): string | undefined {
  const viteEnv = (
    import.meta as unknown as { env?: Record<string, string | undefined> }
  ).env

  const fromVite = viteEnv?.[name]
  if (fromVite !== undefined) return fromVite

  const proc = typeof process === 'undefined' ? undefined : process
  return proc?.env?.[name]
}

function parseBool(value: string): boolean {
  const v = value.trim().toLowerCase()
  return v === '1' || v === 'true' || v === 'yes' || v === 'on'
}

export function getFrontendEnv(): FrontendEnv {
  const backendBaseUrl =
    readEnvValue('VITE_GYSI_BACKEND_BASE_URL')?.trim() || 'http://localhost:8000'

  const useMockRaw = readEnvValue('VITE_GYSI_USE_MOCK')
  const useMock = useMockRaw === undefined ? true : parseBool(useMockRaw)

  return { backendBaseUrl, useMock }
}
