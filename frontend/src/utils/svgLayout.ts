export const NODE_RADIUS = 7
export const NODE_RADIUS_ACTIVE = 10
export const ROW_HEIGHT = 76
export const LANE_WIDTH = 20
export const LEFT_MARGIN = 14

export function nodeX(lane: number): number {
  return LEFT_MARGIN + lane * LANE_WIDTH
}

export function nodeY(yIndex: number): number {
  return yIndex * ROW_HEIGHT + ROW_HEIGHT / 2
}

/** Gerader Pfad bei gleicher x-Position, kubische Bézierkurve bei Abzweigung. */
export function connectorPath(
  from: { x: number; y: number },
  to: { x: number; y: number },
): string {
  if (from.x === to.x) {
    return `M ${from.x} ${from.y} L ${to.x} ${to.y}`
  }
  const midY = (from.y + to.y) / 2
  return `M ${from.x} ${from.y} C ${from.x} ${midY} ${to.x} ${midY} ${to.x} ${to.y}`
}

export function svgHeight(nodeCount: number): number {
  return nodeCount * ROW_HEIGHT
}

export function svgWidth(maxLane: number): number {
  return nodeX(maxLane) + 200
}
