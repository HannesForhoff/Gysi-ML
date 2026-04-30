import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ArtifactRef, ResultResponse, SpecSummary } from '../types'
import { InfoPanel } from './InfoPanel'

const noArtifacts: ArtifactRef[] = []

function makeSpecSummary(stepTypes: string[]): SpecSummary {
  return {
    spec_version_id: 'v99',
    steps: stepTypes.map((t) => ({ step_type: t, enabled: true })),
  }
}

function makeLastRun(stepTypes: string[]): ResultResponse {
  return {
    type: 'result',
    message: '',
    status: 'done',
    step_results: stepTypes.map((t) => ({
      step_type: t,
      metadata: { threshold: 0.9 },
    })),
  }
}

describe('InfoPanel — step_type-basiertes Matching (Bug 1.13 Fix C)', () => {
  it('zeigt keinen Step-Detail wenn der step_type nicht mit dem Spec-Step übereinstimmt', () => {
    // specSummary: 2 Steps (impute_missing, time_feature_encoding)
    // step_results: 1 Step (correlation_filter) — anderer Typ
    // → Aktive Pipeline darf für impute_missing/time_feature_encoding KEIN Detail zeigen
    const specSummary = makeSpecSummary(['impute_missing', 'time_feature_encoding'])
    const lastRun = makeLastRun(['correlation_filter'])

    const { container } = render(
      <InfoPanel specSummary={specSummary} lastRun={lastRun} artifacts={noArtifacts} />,
    )

    // Alle Spec-Steps in der "Aktive Pipeline"-Sektion
    const pipelineSteps = container.querySelectorAll('.infoPipelineStep')
    expect(pipelineSteps).toHaveLength(2) // impute_missing + time_feature_encoding

    // Keiner der beiden Spec-Steps darf ein StepDetail-Element haben
    // (weil deren step_types nicht 'correlation_filter' sind → find() gibt undefined zurück)
    pipelineSteps.forEach((step) => {
      expect(step.querySelector('.infoPipelineStepDetail')).toBeNull()
    })
  })

  it('zeigt den Step-Detail wenn step_type mit Spec-Step übereinstimmt', () => {
    // specSummary: [correlation_filter]
    // step_results: [correlation_filter] — gleicher Typ → Detail wird gezeigt
    const specSummary = makeSpecSummary(['correlation_filter'])
    const lastRun = makeLastRun(['correlation_filter'])

    const { container } = render(
      <InfoPanel specSummary={specSummary} lastRun={lastRun} artifacts={noArtifacts} />,
    )

    const pipelineSteps = container.querySelectorAll('.infoPipelineStep')
    expect(pipelineSteps).toHaveLength(1)

    // Der Step hat ein StepDetail-Element (step_type matcht → sr ist definiert)
    expect(pipelineSteps[0].querySelector('.infoPipelineStepDetail')).not.toBeNull()
  })
})

