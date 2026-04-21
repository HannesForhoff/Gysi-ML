import type { VersionNode } from '../types'

export interface DisplayNode extends VersionNode {
  depth: number
}

export interface LanedNode extends DisplayNode {
  lane: number
  y: number
}

export const LANE_COLORS = [
  '#00008C', // Lane 0: Akzentfarbe (blau)
  '#38a169', // Lane 1: grün
  '#805ad5', // Lane 2: lila
  '#dd6b20', // Lane 3: orange
  '#2b6cb0', // Lane 4: mittelblau
]

/**
 * Wandelt eine flache Liste von VersionNodes in eine Pre-Order-DFS-Reihenfolge um.
 * Jeder Node erhält ein `depth`-Feld (Abstand von der Wurzel, root = 0).
 * Nodes ohne gültigen parent_spec_id-Anteil werden als Roots (depth=0) behandelt.
 */
export function buildVersionTree(versions: VersionNode[]): DisplayNode[] {
  if (versions.length === 0) return []

  const byId = new Map(versions.map((v) => [v.spec_id, v]))
  const children = new Map<string, VersionNode[]>()
  const roots: VersionNode[] = []

  for (const v of versions) {
    if (v.parent_spec_id && byId.has(v.parent_spec_id)) {
      const arr = children.get(v.parent_spec_id) ?? []
      arr.push(v)
      children.set(v.parent_spec_id, arr)
    } else {
      roots.push(v)
    }
  }

  const result: DisplayNode[] = []

  function dfs(node: VersionNode, depth: number): void {
    result.push({ ...node, depth })
    const kids = children.get(node.spec_id) ?? []
    for (const child of kids) {
      dfs(child, depth + 1)
    }
  }

  for (const root of roots) {
    dfs(root, 0)
  }

  return result
}

/**
 * Weist jedem DisplayNode eine Lane (horizontale Spur) und einen y-Index zu.
 * Lane 0 = Hauptast (erster Pfad), Branches bekommen neue Lanes.
 * Nodes werden in der Reihenfolge von buildVersionTree (Pre-Order-DFS) erwartet.
 */
export function assignLanes(nodes: DisplayNode[]): LanedNode[] {
  const result: LanedNode[] = []
  const laneByNodeId = new Map<string, number>()
  let nextLane = 0

  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i]
    let lane: number

    if (!node.parent_spec_id) {
      // Root-Node: erste Root = Lane 0, weitere Roots = neue Lane
      lane = nextLane++
    } else {
      const parentLane = laneByNodeId.get(node.parent_spec_id) ?? 0
      // Erstes Kind auf der Parent-Lane → behält die Parent-Lane (Fortsetzung)
      // Weitere Kinder derselben Parent auf derselben Lane → neuer Branch
      const siblingsOnParentLane = result.filter(
        (n) => n.parent_spec_id === node.parent_spec_id && n.lane === parentLane,
      )
      lane = siblingsOnParentLane.length === 0 ? parentLane : nextLane++
    }

    laneByNodeId.set(node.spec_id, lane)
    result.push({ ...node, lane, y: i })
  }

  return result
}
