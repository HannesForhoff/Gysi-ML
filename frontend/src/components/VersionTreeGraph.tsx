import { useState } from 'react'
import type { VersionTree } from '../types'
import { LANE_COLORS, assignLanes, buildVersionTree } from '../utils/buildVersionTree'
import {
  NODE_RADIUS,
  NODE_RADIUS_ACTIVE,
  connectorPath,
  nodeX,
  nodeY,
  svgHeight,
  svgWidth,
} from '../utils/svgLayout'

type VersionTreeGraphProps = {
  specHistory: VersionTree
  onRollback: (specId: string) => void
  isRollingBack: boolean
  rollbackTargetId: string | null
}

function runStatusColor(status: string | null): string {
  if (status === 'done') return '#38a169'
  if (status === 'failed') return '#e53e3e'
  return '#cbd5e0'
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('de-DE', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

export function VersionTreeGraph({
  specHistory,
  onRollback,
  isRollingBack,
  rollbackTargetId,
}: VersionTreeGraphProps) {
  const [openNodeId, setOpenNodeId] = useState<string | null>(null)

  const displayNodes = buildVersionTree(specHistory.versions)
  const lanedNodes = assignLanes(displayNodes)
  const activeId = specHistory.active_spec_id

  const maxLane = lanedNodes.length === 0 ? 0 : Math.max(...lanedNodes.map((n) => n.lane))
  const width = svgWidth(maxLane)
  const height = svgHeight(lanedNodes.length)

  // Text labels start to the right of the rightmost lane
  const textStartX = nodeX(maxLane) + NODE_RADIUS_ACTIVE + 12

  const nodeById = new Map(lanedNodes.map((n) => [n.spec_id, n]))
  const openNode = openNodeId ? (nodeById.get(openNodeId) ?? null) : null

  return (
    <div className="versionTreeGraph">
      <svg
        className="versionTreeSvg"
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
      >
        {/* Connector paths – rendered first so circles appear on top */}
        {lanedNodes.map((node) => {
          if (!node.parent_spec_id) return null
          const parent = nodeById.get(node.parent_spec_id)
          if (!parent) return null
          const from = { x: nodeX(parent.lane), y: nodeY(parent.y) }
          const to = { x: nodeX(node.lane), y: nodeY(node.y) }
          const color = LANE_COLORS[node.lane % LANE_COLORS.length]
          const d = connectorPath(from, to)
          return (
            <path
              key={`conn-${node.spec_id}`}
              d={d}
              stroke={color}
              strokeWidth={2}
              fill="none"
              opacity={0.75}
            />
          )
        })}

        {/* Node groups */}
        {lanedNodes.map((node) => {
          const isActive = node.spec_id === activeId
          const isOpen = openNodeId === node.spec_id
          const isRollbackNode = node.change_summary?.startsWith('Rollback') ?? false
          const isBaseNode = !node.parent_spec_id
          const nodeColor = isBaseNode ? '#ea7c1e' : LANE_COLORS[node.lane % LANE_COLORS.length]
          const cx = nodeX(node.lane)
          const cy = nodeY(node.y)
          const radius = isActive ? NODE_RADIUS_ACTIVE : NODE_RADIUS

          return (
            <g key={node.spec_id}>
              {/* Selection ring (appears when node detail card is open) */}
              {isOpen && (
                <circle
                  cx={cx}
                  cy={cy}
                  r={radius + 5}
                  fill="none"
                  stroke={nodeColor}
                  strokeWidth={1.5}
                  opacity={0.45}
                  pointerEvents="none"
                />
              )}

              {/* Node circle */}
              <circle
                data-testid="node-circle"
                cx={cx}
                cy={cy}
                r={radius}
                fill={nodeColor}
                stroke={isActive ? '#ffffff' : 'none'}
                strokeWidth={isActive ? 2.5 : 0}
                style={{ cursor: 'pointer' }}
                onClick={() => setOpenNodeId(isOpen ? null : node.spec_id)}
              />

              {/* Version label – row 1 */}
              <text
                x={textStartX}
                y={cy - 7}
                fontSize={13}
                fontFamily="monospace"
                fontWeight={700}
                fill="var(--text-h, #1e293b)"
                style={{ userSelect: 'none' }}
              >
                {isRollbackNode ? '↩ ' : ''}
                {node.version}
              </text>

              {/* Run-status dot – row 1, right of version */}
              <circle
                cx={textStartX + 76}
                cy={cy - 11}
                r={4}
                fill={runStatusColor(node.last_run_status)}
              />

              {/* Phase badge – row 2 */}
              <text
                x={textStartX}
                y={cy + 11}
                fontSize={11}
                fontFamily="monospace"
                fontWeight={600}
                fill={isBaseNode ? '#ea7c1e' : node.phase === 'modeling' ? '#276749' : '#2b6cb0'}
                style={{ userSelect: 'none' }}
              >
                {isBaseNode ? 'Rohdaten' : node.phase === 'modeling' ? 'Modeling' : 'Preprocessing'}
              </text>

              {/* Active indicator – row 2, right of phase */}
              {isActive && (
                <text
                  x={textStartX + 95}
                  y={cy + 11}
                  fontSize={10}
                  fontFamily="monospace"
                  fontWeight={700}
                  fill="var(--accent, #00008C)"
                  style={{ userSelect: 'none' }}
                >
                  ■ Aktiv
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {/* Node detail card – rendered as HTML below the SVG, avoids all SVG overflow issues */}
      {openNode && (
        <div className="nodeInfoCard">
          <div className="nodeInfoCard__header">
            <span className="nodeInfoCard__version">
              {openNode.change_summary?.startsWith('Rollback') ? '↩ ' : ''}
              {openNode.version}
            </span>
            <span
              className={`nodeInfoCard__phaseBadge nodeInfoCard__phaseBadge--${openNode.parent_spec_id ? openNode.phase : 'rohdaten'}`}
            >
              {openNode.parent_spec_id
                ? openNode.phase === 'modeling'
                  ? 'Modeling'
                  : 'Preprocessing'
                : 'Rohdaten'}
            </span>
            {openNode.spec_id === activeId && (
              <span className="nodeInfoCard__activeBadge">■ Aktiv</span>
            )}
          </div>
          <div className="nodeInfoCard__summary">
            {openNode.change_summary ?? (!openNode.parent_spec_id ? 'Ausgangszustand (Rohdaten)' : '—')}
          </div>
          <div className="nodeInfoCard__meta">
            <span>{formatDate(openNode.created_at)}</span>
            {openNode.last_run_status && (
              <span style={{ color: runStatusColor(openNode.last_run_status) }}>
                ● {openNode.last_run_status}
              </span>
            )}
          </div>
          {openNode.spec_id !== activeId && (
            <button
              className="nodeInfoCard__rollbackBtn"
              onClick={() => onRollback(openNode.spec_id)}
              disabled={isRollingBack}
            >
              {isRollingBack && rollbackTargetId === openNode.spec_id
                ? '…'
                : `↩ Rollback zu ${openNode.version}`}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
