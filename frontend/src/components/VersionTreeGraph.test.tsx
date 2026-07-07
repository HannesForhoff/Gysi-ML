import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { VersionTree } from '../types'
import { VersionTreeGraph } from './VersionTreeGraph'

function makeVersionTree(overrides?: Partial<VersionTree>): VersionTree {
  return {
    session_id: 'sess-1',
    active_spec_id: 'id-1',
    versions: [
      {
        spec_id: 'id-1',
        version: 'v1',
        parent_spec_id: null,
        change_summary: null,
        created_at: '2026-01-01T00:00:00Z',
        has_runs: false,
        last_run_status: null,
        last_run_id: null,
        phase: 'preprocessing',
      },
      {
        spec_id: 'id-2',
        version: 'v2',
        parent_spec_id: 'id-1',
        change_summary: 'Imputation hinzugefügt',
        created_at: '2026-01-02T00:00:00Z',
        has_runs: false,
        last_run_status: null,
        last_run_id: null,
        phase: 'preprocessing',
      },
      {
        spec_id: 'id-3',
        version: 'v3',
        parent_spec_id: 'id-2',
        change_summary: 'Encoding konfiguriert',
        created_at: '2026-01-03T00:00:00Z',
        has_runs: true,
        last_run_status: 'done',
        last_run_id: 'run-1',
        phase: 'modeling',
      },
    ],
    ...overrides,
  }
}

describe('VersionTreeGraph', () => {
  it('rendert SVG mit 3 node-circles und 2 connector-paths für lineare Kette', () => {
    const { container } = render(
      <VersionTreeGraph
        specHistory={makeVersionTree()}
        onRollback={vi.fn()}
        isRollingBack={false}
        rollbackTargetId={null}
      />,
    )

    const circles = container.querySelectorAll('[data-testid="node-circle"]')
    expect(circles).toHaveLength(3)

    const paths = container.querySelectorAll('path')
    expect(paths).toHaveLength(2)
  })

  it('rendert SVG-Element innerhalb .versionTreeGraph', () => {
    const { container } = render(
      <VersionTreeGraph
        specHistory={makeVersionTree()}
        onRollback={vi.fn()}
        isRollingBack={false}
        rollbackTargetId={null}
      />,
    )
    expect(container.querySelector('.versionTreeGraph')).not.toBeNull()
    expect(container.querySelector('.versionTreeSvg')).not.toBeNull()
  })

  it('zeigt Rollback-Button in Infokarte nur für inaktive Nodes', () => {
    const tree = makeVersionTree({ active_spec_id: 'id-1' })
    const { container, queryAllByRole } = render(
      <VersionTreeGraph
        specHistory={tree}
        onRollback={vi.fn()}
        isRollingBack={false}
        rollbackTargetId={null}
      />,
    )
    // Kein Node angeklickt – keine Buttons sichtbar
    expect(queryAllByRole('button')).toHaveLength(0)

    const circles = container.querySelectorAll('[data-testid="node-circle"]')

    // Inaktiven Node (id-2) anklicken – Rollback-Button erscheint
    fireEvent.click(circles[1])
    expect(queryAllByRole('button')).toHaveLength(1)
    expect(screen.getByRole('button')).toHaveTextContent('Im Tree wiederherstellen: v2')

    // Aktiven Node (id-1) anklicken – kein Rollback-Button
    fireEvent.click(circles[0])
    expect(queryAllByRole('button')).toHaveLength(0)
  })

  it('leere versions-Liste rendert SVG mit 0 circles', () => {
    const tree = makeVersionTree({ versions: [], active_spec_id: null })
    const { container } = render(
      <VersionTreeGraph
        specHistory={tree}
        onRollback={vi.fn()}
        isRollingBack={false}
        rollbackTargetId={null}
      />,
    )
    const circles = container.querySelectorAll('[data-testid="node-circle"]')
    expect(circles).toHaveLength(0)
  })

  it('isRollingBack=true deaktiviert den Rollback-Button in der Infokarte', () => {
    const tree = makeVersionTree({ active_spec_id: 'id-1' })
    const { container, getByRole } = render(
      <VersionTreeGraph
        specHistory={tree}
        onRollback={vi.fn()}
        isRollingBack={true}
        rollbackTargetId={null}
      />,
    )
    // Inaktiven Node anklicken, damit die Infokarte erscheint
    const circles = container.querySelectorAll('[data-testid="node-circle"]')
    fireEvent.click(circles[1])

    expect(getByRole('button')).toBeDisabled()
  })
})
