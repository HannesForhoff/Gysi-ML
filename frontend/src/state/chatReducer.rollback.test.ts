import { describe, expect, it } from 'vitest'

import { chatReducer, createInitialChatState } from './chatReducer'
import type { ChatMessage, VersionNode, VersionTree } from '../types'

const infoMessage: ChatMessage = {
  id: 'info-1',
  role: 'assistant',
  content: 'Rollback abgeschlossen.',
  ts: new Date().toISOString(),
}

const emptyTree: VersionTree = {
  session_id: 'session-abc',
  active_spec_id: 'spec-v1',
  versions: [],
}

// ---------------------------------------------------------------------------
// ROLLBACK_SUCCEEDED — activeDataRunId (DV-2.4)
// ---------------------------------------------------------------------------

describe('chatReducer — ROLLBACK_SUCCEEDED setzt activeDataRunId', () => {
  it('setzt activeDataRunId auf übergebene run_id wenn Run vorhanden', () => {
    const state = createInitialChatState()
    const next = chatReducer(state, {
      type: 'ROLLBACK_SUCCEEDED',
      infoMessage,
      specTree: emptyTree,
      specSummary: null,
      activeDataRunId: 'run-123',
    })
    expect(next.activeDataRunId).toBe('run-123')
  })

  it('setzt activeDataRunId auf null wenn Rollback zu Spec ohne Run', () => {
    const state = { ...createInitialChatState(), activeDataRunId: 'run-previous' }
    const next = chatReducer(state, {
      type: 'ROLLBACK_SUCCEEDED',
      infoMessage,
      specTree: emptyTree,
      specSummary: null,
      activeDataRunId: null,
    })
    expect(next.activeDataRunId).toBeNull()
  })

  it('setzt ui auf idle nach Rollback', () => {
    const state = { ...createInitialChatState(), ui: { type: 'run_polling' } as const }
    const next = chatReducer(state, {
      type: 'ROLLBACK_SUCCEEDED',
      infoMessage,
      specTree: emptyTree,
      specSummary: null,
      activeDataRunId: 'run-456',
    })
    expect(next.ui.type).toBe('idle')
  })

  it('hängt infoMessage an messages an', () => {
    const state = createInitialChatState()
    const next = chatReducer(state, {
      type: 'ROLLBACK_SUCCEEDED',
      infoMessage,
      specTree: emptyTree,
      specSummary: null,
      activeDataRunId: null,
    })
    expect(next.messages).toContain(infoMessage)
  })
})

// ---------------------------------------------------------------------------
// resolveActiveDataRunId — handleRollback Ableitungslogik (M2-Fix)
// Testet den Algorithmus aus App.tsx handleRollback:
//   (newTree ?? fallbackTree)?.versions.find(v => v.spec_id === id)?.last_run_id ?? null
// ---------------------------------------------------------------------------

function makeNode(spec_id: string, last_run_id: string | null): VersionNode {
  return {
    spec_id,
    version: 'v1',
    parent_spec_id: null,
    change_summary: null,
    created_at: '2026-01-01T00:00:00Z',
    has_runs: last_run_id !== null,
    last_run_status: last_run_id !== null ? 'done' : null,
    last_run_id,
  }
}

function resolveActiveDataRunId(
  newTree: VersionTree | null,
  fallbackTree: VersionTree | null,
  targetSpecId: string,
): string | null {
  const treeForLookup = newTree ?? fallbackTree
  return treeForLookup?.versions.find(v => v.spec_id === targetSpecId)?.last_run_id ?? null
}

describe('resolveActiveDataRunId — handleRollback Logik (DV-2.4)', () => {
  it('gibt last_run_id zurück wenn Ziel-Spec einen Run hat', () => {
    const tree: VersionTree = {
      session_id: 'sess-1',
      active_spec_id: 'spec-2',
      versions: [makeNode('spec-1', 'run-old'), makeNode('spec-2', 'run-new')],
    }
    expect(resolveActiveDataRunId(tree, null, 'spec-1')).toBe('run-old')
    expect(resolveActiveDataRunId(tree, null, 'spec-2')).toBe('run-new')
  })

  it('gibt null zurück wenn Ziel-Spec keinen Run hat', () => {
    const tree: VersionTree = {
      session_id: 'sess-1',
      active_spec_id: 'spec-1',
      versions: [makeNode('spec-1', null)],
    }
    expect(resolveActiveDataRunId(tree, null, 'spec-1')).toBeNull()
  })

  it('gibt null zurück wenn Spec nicht im Tree gefunden', () => {
    const tree: VersionTree = {
      session_id: 'sess-1',
      active_spec_id: 'spec-1',
      versions: [makeNode('spec-1', 'run-abc')],
    }
    expect(resolveActiveDataRunId(tree, null, 'spec-does-not-exist')).toBeNull()
  })

  it('verwendet fallbackTree wenn newTree null ist (M1-Fix)', () => {
    const fallback: VersionTree = {
      session_id: 'sess-1',
      active_spec_id: 'spec-1',
      versions: [makeNode('spec-1', 'run-fallback')],
    }
    expect(resolveActiveDataRunId(null, fallback, 'spec-1')).toBe('run-fallback')
  })

  it('gibt null zurück wenn sowohl newTree als auch fallbackTree null sind', () => {
    expect(resolveActiveDataRunId(null, null, 'spec-1')).toBeNull()
  })
})
