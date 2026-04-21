import { describe, expect, it } from 'vitest'
import type { VersionNode } from '../types'
import { assignLanes, buildVersionTree } from './buildVersionTree'

function makeNode(overrides: Partial<VersionNode> & { spec_id: string; version: string }): VersionNode {
  return {
    parent_spec_id: null,
    change_summary: null,
    created_at: '2026-01-01T00:00:00Z',
    has_runs: false,
    last_run_status: null,
    last_run_id: null,
    phase: 'preprocessing',
    ...overrides,
  }
}

describe('buildVersionTree', () => {
  it('gibt eine leere Liste zurück wenn keine Nodes übergeben', () => {
    expect(buildVersionTree([])).toEqual([])
  })

  it('einzelner Node hat depth=0', () => {
    const v1 = makeNode({ spec_id: 'id-1', version: 'v1' })
    const result = buildVersionTree([v1])
    expect(result).toHaveLength(1)
    expect(result[0].depth).toBe(0)
    expect(result[0].spec_id).toBe('id-1')
  })

  it('lineare Kette v1→v2→v3: korrekte Reihenfolge und depths', () => {
    const v1 = makeNode({ spec_id: 'id-1', version: 'v1', parent_spec_id: null })
    const v2 = makeNode({ spec_id: 'id-2', version: 'v2', parent_spec_id: 'id-1' })
    const v3 = makeNode({ spec_id: 'id-3', version: 'v3', parent_spec_id: 'id-2' })

    const result = buildVersionTree([v1, v2, v3])

    expect(result).toHaveLength(3)
    expect(result[0]).toMatchObject({ spec_id: 'id-1', depth: 0 })
    expect(result[1]).toMatchObject({ spec_id: 'id-2', depth: 1 })
    expect(result[2]).toMatchObject({ spec_id: 'id-3', depth: 2 })
  })

  it('branch bei v1→v2 und v1→v3: Pre-Order-DFS mit depth', () => {
    // v1 ist Root, hat zwei Kinder: v2 und v3
    const v1 = makeNode({ spec_id: 'id-1', version: 'v1', parent_spec_id: null })
    const v2 = makeNode({ spec_id: 'id-2', version: 'v2', parent_spec_id: 'id-1' })
    const v3 = makeNode({ spec_id: 'id-3', version: 'v3', parent_spec_id: 'id-1' })

    const result = buildVersionTree([v1, v2, v3])

    expect(result).toHaveLength(3)
    expect(result[0]).toMatchObject({ spec_id: 'id-1', depth: 0 })
    // DFS: v2 kommt nach v1 (erstes Kind), dann v3
    expect(result[1]).toMatchObject({ spec_id: 'id-2', depth: 1 })
    expect(result[2]).toMatchObject({ spec_id: 'id-3', depth: 1 })
  })

  it('echter Rollback-Branch: v1→v2→v3→v4 und v2→v5', () => {
    const v1 = makeNode({ spec_id: 'id-1', version: 'v1', parent_spec_id: null })
    const v2 = makeNode({ spec_id: 'id-2', version: 'v2', parent_spec_id: 'id-1' })
    const v3 = makeNode({ spec_id: 'id-3', version: 'v3', parent_spec_id: 'id-2' })
    const v4 = makeNode({ spec_id: 'id-4', version: 'v4', parent_spec_id: 'id-3' })
    // Rollback auf v2 → v5 hat parent=v2 (echter Branch)
    const v5 = makeNode({ spec_id: 'id-5', version: 'v5', parent_spec_id: 'id-2', change_summary: 'Rollback auf v2' })

    const result = buildVersionTree([v1, v2, v3, v4, v5])

    expect(result).toHaveLength(5)
    expect(result[0]).toMatchObject({ spec_id: 'id-1', depth: 0 })
    expect(result[1]).toMatchObject({ spec_id: 'id-2', depth: 1 })
    // DFS: v3 und v4 kommen vor v5 (v3 ist das erste Kind von v2)
    expect(result[2]).toMatchObject({ spec_id: 'id-3', depth: 2 })
    expect(result[3]).toMatchObject({ spec_id: 'id-4', depth: 3 })
    expect(result[4]).toMatchObject({ spec_id: 'id-5', depth: 2 })
  })

  it('mehrere Roots (lückenhafte parent_spec_id): alle depth=0', () => {
    const v1 = makeNode({ spec_id: 'id-1', version: 'v1', parent_spec_id: null })
    const v2 = makeNode({ spec_id: 'id-2', version: 'v2', parent_spec_id: 'unknown-id' })

    const result = buildVersionTree([v1, v2])

    expect(result).toHaveLength(2)
    expect(result[0]).toMatchObject({ spec_id: 'id-1', depth: 0 })
    expect(result[1]).toMatchObject({ spec_id: 'id-2', depth: 0 })
  })

  it('originalfelds bleiben erhalten (phase, last_run_id etc.)', () => {
    const v1 = makeNode({
      spec_id: 'id-1',
      version: 'v1',
      phase: 'modeling',
      last_run_id: 'run-42',
      has_runs: true,
      last_run_status: 'done',
    })
    const result = buildVersionTree([v1])

    expect(result[0].phase).toBe('modeling')
    expect(result[0].last_run_id).toBe('run-42')
    expect(result[0].has_runs).toBe(true)
    expect(result[0].last_run_status).toBe('done')
  })
})

describe('assignLanes', () => {
  it('lineare Kette v1→v2→v3: alle Lane 0', () => {
    const v1 = makeNode({ spec_id: 'id-1', version: 'v1', parent_spec_id: null })
    const v2 = makeNode({ spec_id: 'id-2', version: 'v2', parent_spec_id: 'id-1' })
    const v3 = makeNode({ spec_id: 'id-3', version: 'v3', parent_spec_id: 'id-2' })

    const display = buildVersionTree([v1, v2, v3])
    const result = assignLanes(display)

    expect(result).toHaveLength(3)
    expect(result[0]).toMatchObject({ spec_id: 'id-1', lane: 0, y: 0 })
    expect(result[1]).toMatchObject({ spec_id: 'id-2', lane: 0, y: 1 })
    expect(result[2]).toMatchObject({ spec_id: 'id-3', lane: 0, y: 2 })
  })

  it('ein Rollback-Branch: Hauptast Lane 0, Branch Lane 1', () => {
    // Hauptkette: v1→v2→v3→v4, Rollback-Branch: v2→v5
    const v1 = makeNode({ spec_id: 'id-1', version: 'v1', parent_spec_id: null })
    const v2 = makeNode({ spec_id: 'id-2', version: 'v2', parent_spec_id: 'id-1' })
    const v3 = makeNode({ spec_id: 'id-3', version: 'v3', parent_spec_id: 'id-2' })
    const v4 = makeNode({ spec_id: 'id-4', version: 'v4', parent_spec_id: 'id-3' })
    const v5 = makeNode({ spec_id: 'id-5', version: 'v5', parent_spec_id: 'id-2', change_summary: 'Rollback auf v2' })

    const display = buildVersionTree([v1, v2, v3, v4, v5])
    const result = assignLanes(display)

    expect(result).toHaveLength(5)
    // Hauptast
    expect(result.find((n) => n.spec_id === 'id-1')?.lane).toBe(0)
    expect(result.find((n) => n.spec_id === 'id-2')?.lane).toBe(0)
    expect(result.find((n) => n.spec_id === 'id-3')?.lane).toBe(0)
    expect(result.find((n) => n.spec_id === 'id-4')?.lane).toBe(0)
    // Rollback-Branch
    expect(result.find((n) => n.spec_id === 'id-5')?.lane).toBe(1)
  })

  it('zwei unabhängige Branches von Root: Lane 0, 1, 2', () => {
    // v1 hat drei Kinder: v2 (Hauptast), v3 (Branch 1), v4 (Branch 2)
    const v1 = makeNode({ spec_id: 'id-1', version: 'v1', parent_spec_id: null })
    const v2 = makeNode({ spec_id: 'id-2', version: 'v2', parent_spec_id: 'id-1' })
    const v3 = makeNode({ spec_id: 'id-3', version: 'v3', parent_spec_id: 'id-1' })
    const v4 = makeNode({ spec_id: 'id-4', version: 'v4', parent_spec_id: 'id-1' })

    const display = buildVersionTree([v1, v2, v3, v4])
    const result = assignLanes(display)

    expect(result).toHaveLength(4)
    expect(result.find((n) => n.spec_id === 'id-1')?.lane).toBe(0)
    expect(result.find((n) => n.spec_id === 'id-2')?.lane).toBe(0)
    expect(result.find((n) => n.spec_id === 'id-3')?.lane).toBe(1)
    expect(result.find((n) => n.spec_id === 'id-4')?.lane).toBe(2)
  })

  it('y-Index entspricht Pre-Order-DFS-Reihenfolge', () => {
    const v1 = makeNode({ spec_id: 'id-1', version: 'v1', parent_spec_id: null })
    const v2 = makeNode({ spec_id: 'id-2', version: 'v2', parent_spec_id: 'id-1' })
    const v3 = makeNode({ spec_id: 'id-3', version: 'v3', parent_spec_id: 'id-2' })

    const display = buildVersionTree([v1, v2, v3])
    const result = assignLanes(display)

    expect(result[0].y).toBe(0)
    expect(result[1].y).toBe(1)
    expect(result[2].y).toBe(2)
  })
})

