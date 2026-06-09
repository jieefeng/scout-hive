import { useCallback, useMemo } from 'react';
import { ReactFlow, Background, Controls, Handle, Position, type Node, type Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

interface DagEdge { from_node?: string; from?: string; to_node?: string; to?: string; }
interface DagNode { id: string; agent: string; action: string; depends_on?: string[]; params?: { dimension?: string } }
interface DagBlueprint { nodes?: DagNode[]; edges?: DagEdge[]; feedback_edges?: DagEdge[]; }

interface NodeInfo {
  agent: string;        // "Collector" | "Analyst" | "Writer" | "Reviewer"
  competitor: string;   // "豆包"
  dimension: string;    // "核心玩法"
}

const AGENT_MAP: Record<string, string> = { c: 'Collector', a: 'Analyst', w: 'Writer', r: 'Reviewer' };

function parseNodeInfo(id: string, dagBlueprint?: DagBlueprint | null): NodeInfo {
  // 优先从 dagBlueprint 读取
  if (dagBlueprint?.nodes) {
    const node = dagBlueprint.nodes.find(n => n.id === id);
    if (node) {
      const prefix = id.split('_')[0];
      return {
        agent: node.agent || AGENT_MAP[prefix] || '',
        competitor: id.split('_').slice(1, -1).join('_') || '',
        dimension: node.params?.dimension || '',
      };
    }
  }
  // 降级：从 ID 解析 — format: prefix_competitor_dimension
  const parts = id.split('_');
  const prefix = parts[0];
  return {
    agent: AGENT_MAP[prefix] || '',
    competitor: parts.length >= 3 ? parts.slice(1, -1).join('_') : '',
    dimension: parts.length >= 3 ? parts.slice(-1)[0] : '',
  };
}

interface SwimlaneGroup {
  competitor: string;
  color: string;          // 泳道底色
  borderColor: string;    // 泳道边框色
  dimGroups: {
    dimension: string;
    nodes: string[];      // [collector_id, analyst_id, writer_id] 按 C→A→W 排序
  }[];
}

const SWIMLANE_COLORS = [
  { bg: '#eff6ff', border: '#bfdbfe' },  // 蓝
  { bg: '#f0fdf4', border: '#bbf7d0' },  // 绿
  { bg: '#fefce8', border: '#fde68a' },  // 黄
  { bg: '#fdf4ff', border: '#d8b4fe' },  // 紫
  { bg: '#fef2f2', border: '#fecaca' },  // 红
];

const AGENT_ORDER = { Collector: 0, Analyst: 1, Writer: 2, Reviewer: 3 };

function groupByCompetitor(nodeIds: string[], dagBlueprint?: DagBlueprint | null): SwimlaneGroup[] {
  const competitorMap = new Map<string, Map<string, string[]>>();

  for (const id of nodeIds) {
    const info = parseNodeInfo(id, dagBlueprint);
    if (!info.competitor) continue;  // 无法解析的节点跳过分组

    if (!competitorMap.has(info.competitor)) {
      competitorMap.set(info.competitor, new Map());
    }
    const dimMap = competitorMap.get(info.competitor)!;
    if (!dimMap.has(info.dimension)) {
      dimMap.set(info.dimension, []);
    }
    dimMap.get(info.dimension)!.push(id);
  }

  return Array.from(competitorMap.entries()).map(([competitor, dimMap], index) => ({
    competitor,
    color: SWIMLANE_COLORS[index % SWIMLANE_COLORS.length].bg,
    borderColor: SWIMLANE_COLORS[index % SWIMLANE_COLORS.length].border,
    dimGroups: Array.from(dimMap.entries()).map(([dimension, ids]) => ({
      dimension,
      nodes: ids.sort((a, b) => {
        const infoA = parseNodeInfo(a, dagBlueprint);
        const infoB = parseNodeInfo(b, dagBlueprint);
        return (AGENT_ORDER[infoA.agent as keyof typeof AGENT_ORDER] ?? 99)
             - (AGENT_ORDER[infoB.agent as keyof typeof AGENT_ORDER] ?? 99);
      }),
    })),
  }));
}

interface DagViewerProps {
  nodeStates: Record<string, string>;
  dagBlueprint?: DagBlueprint | null;
  onNodeClick?: (nodeId: string) => void;
  selectedNodeId?: string | null;
}

const STATUS_DOT_COLORS: Record<string, string> = {
  pending: '#94a3b8', running: '#3b82f6', completed: '#22c55e',
  failed: '#ef4444', skipped: '#f59e0b',
};

const STATUS_LABELS: Record<string, string> = {
  pending: '等待', running: '运行中', completed: '完成',
  failed: '失败', skipped: '跳过',
};

const NODE_W = 120;
const NODE_H = 80;
const NODE_GAP = 12;
const DIM_GROUP_GAP = 32;
const SWIMLANE_GAP = 20;
const SWIMLANE_HEADER = 40;
const SWIMLANE_PADDING = 16;

interface DagNodeComponentProps {
  data: {
    label: string;
    agent?: string;
    dimension?: string;
    competitor?: string;
    status?: string;
  };
}

const AGENT_LABELS: Record<string, string> = {
  Collector: "数据采集",
  Analyst: "结构分析",
  Writer: "报告写作",
  Reviewer: "质量审查",
};

const AGENT_ACCENT: Record<string, string> = {
  Collector: '#3b82f6',
  Analyst: '#8b5cf6',
  Writer: '#10b981',
  Reviewer: '#f59e0b',
};

function DagNodeComponent({ data }: DagNodeComponentProps) {
  const { label, agent, dimension, competitor, status } = data;

  const agentMap: Record<string, string> = { c: 'Collector', a: 'Analyst', w: 'Writer', r: 'Reviewer' };
  const prefix = label.split('_')[0];
  const agentName = agentMap[prefix] || agent || label;

  const accent = AGENT_ACCENT[agentName] || '#64748b';
  const dotColor = STATUS_DOT_COLORS[status || 'pending'] || '#94a3b8';
  const statusLabel = STATUS_LABELS[status || 'pending'] || '等待';

  return (
    <>
      <Handle type="target" position={Position.Top} style={{ visibility: 'hidden' }} />
      <div style={{ textAlign: 'center', lineHeight: 1.2 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px', marginBottom: '6px' }}>
          <span style={{
            width: '8px', height: '8px', borderRadius: '50%', background: dotColor,
            animation: status === 'running' ? 'pulse 1.5s infinite' : 'none',
          }} />
          <span style={{ fontSize: '9px', color: '#64748b', fontWeight: 500 }}>{statusLabel}</span>
        </div>
        <div style={{ fontSize: '11px', fontWeight: 700, color: '#1e293b', marginBottom: '4px' }}>
          {AGENT_LABELS[agentName] || agentName}
        </div>
        {dimension && (
          <div style={{
            fontSize: '9px', color: accent, fontWeight: 600,
            background: `${accent}15`, padding: '2px 8px', borderRadius: '4px',
            display: 'inline-block', maxWidth: '100px',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>{dimension}</div>
        )}
        {competitor && (
          <div style={{
            fontSize: '8px', color: '#94a3b8', marginTop: '4px',
            maxWidth: '100px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>{competitor}</div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ visibility: 'hidden' }} />
    </>
  );
}

function SwimlaneBackground({ data }: { data: SwimlaneGroup & { laneIndex: number } }) {
  const { competitor, color, borderColor, dimGroups } = data;
  const totalNodes = dimGroups.reduce((sum, g) => sum + g.nodes.length, 0);
  const totalGaps = Math.max(0, dimGroups.length - 1);
  const width = totalNodes * (NODE_W + NODE_GAP) - NODE_GAP + totalGaps * DIM_GROUP_GAP;
  const height = SWIMLANE_HEADER + SWIMLANE_PADDING * 2 + NODE_H;

  return (
    <div style={{
      width, height, background: color, border: `1px solid ${borderColor}`,
      borderRadius: '12px', position: 'relative',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '8px 16px', borderBottom: `1px solid ${borderColor}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '3px', background: AGENT_ACCENT['Collector'] || '#3b82f6' }} />
          <strong style={{ fontSize: '13px', color: '#1e293b' }}>{competitor}</strong>
        </div>
      </div>
      {dimGroups.map((group, i) => {
        const prevNodes = dimGroups.slice(0, i).reduce((s, g) => s + g.nodes.length, 0);
        const groupX = prevNodes * (NODE_W + NODE_GAP) + i * DIM_GROUP_GAP;
        return (
          <div key={group.dimension} style={{
            position: 'absolute', left: groupX, bottom: '4px',
            fontSize: '9px', color: '#94a3b8', textAlign: 'center',
            width: group.nodes.length * (NODE_W + NODE_GAP) - NODE_GAP,
          }}>
            {group.dimension}
          </div>
        );
      })}
    </div>
  );
}

const NODE_TYPES = { default: DagNodeComponent, swimlane: SwimlaneBackground };

export default function DagViewer({ nodeStates, dagBlueprint, onNodeClick, selectedNodeId }: DagViewerProps) {
  const nodes: Node[] = useMemo(() => {
    const blueprintNodes = dagBlueprint?.nodes || [];
    const allIds = blueprintNodes.length > 0
      ? blueprintNodes.map(n => n.id)
      : Object.keys(nodeStates);

    const swimlanes = groupByCompetitor(allIds, dagBlueprint);

    // Fallback: grid layout when no swimlanes
    if (swimlanes.length === 0) {
      const cols = Math.max(1, Math.ceil(Math.sqrt(allIds.length)));
      return allIds.map((id, index) => {
        const info = parseNodeInfo(id, dagBlueprint);
        const status = nodeStates[id] || 'pending';
        const isSelected = id === selectedNodeId;
        return {
          id,
          type: 'default' as const,
          position: {
            x: (NODE_W + NODE_GAP) * (index % cols),
            y: (NODE_H + NODE_GAP) * Math.floor(index / cols),
          },
          data: { label: id, agent: info.agent, dimension: info.dimension, competitor: info.competitor, status },
          style: {
            width: NODE_W,
            height: NODE_H,
            border: `1px solid ${isSelected ? '#3b82f6' : '#e2e8f0'}`,
            borderRadius: '12px',
            padding: '10px',
            background: isSelected ? '#dbeafe' : 'linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)',
            boxShadow: isSelected
              ? '0 0 0 3px rgba(59,130,246,0.2), 0 4px 12px rgba(0,0,0,0.08)'
              : '0 1px 3px rgba(0,0,0,0.06), 0 4px 12px rgba(0,0,0,0.04)',
            cursor: 'pointer',
            transition: 'box-shadow 0.2s, border-color 0.2s',
          },
        };
      });
    }

    // Swimlane layout
    const result: Node[] = [];
    let currentY = 0;

    let laneIndex = 0;
    for (const lane of swimlanes) {
      const totalNodes = lane.dimGroups.reduce((sum, g) => sum + g.nodes.length, 0);
      const totalGaps = Math.max(0, lane.dimGroups.length - 1);
      const laneWidth = totalNodes * (NODE_W + NODE_GAP) - NODE_GAP + totalGaps * DIM_GROUP_GAP;

      // Swimlane background node
      result.push({
        id: `swimlane-${lane.competitor}`,
        type: 'swimlane' as any,
        position: { x: -SWIMLANE_PADDING, y: currentY },
        data: { ...lane, laneIndex },
        style: { width: laneWidth + SWIMLANE_PADDING * 2, height: SWIMLANE_HEADER + SWIMLANE_PADDING * 2 + NODE_H },
        zIndex: -1,
        selectable: false,
        draggable: false,
      } as any);

      // Nodes within the swimlane
      let nodeIndexInLane = 0;
      for (const dimGroup of lane.dimGroups) {
        for (let i = 0; i < dimGroup.nodes.length; i++) {
          const id = dimGroup.nodes[i];
          const info = parseNodeInfo(id, dagBlueprint);
          const status = nodeStates[id] || 'pending';
          const isSelected = id === selectedNodeId;

          result.push({
            id,
            type: 'default' as const,
            position: {
              x: nodeIndexInLane * (NODE_W + NODE_GAP),
              y: currentY + SWIMLANE_HEADER + SWIMLANE_PADDING,
            },
            data: { label: id, agent: info.agent, dimension: info.dimension, competitor: info.competitor, status },
            style: {
              width: NODE_W,
              height: NODE_H,
              border: `1px solid ${isSelected ? '#3b82f6' : '#e2e8f0'}`,
              borderRadius: '12px',
              padding: '10px',
              background: isSelected ? '#dbeafe' : 'linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)',
              boxShadow: isSelected
                ? '0 0 0 3px rgba(59,130,246,0.2), 0 4px 12px rgba(0,0,0,0.08)'
                : '0 1px 3px rgba(0,0,0,0.06), 0 4px 12px rgba(0,0,0,0.04)',
              cursor: 'pointer',
              transition: 'box-shadow 0.2s, border-color 0.2s',
            },
          });
          nodeIndexInLane++;
        }
        nodeIndexInLane++; // gap between dimension groups
      }
      currentY += SWIMLANE_HEADER + SWIMLANE_PADDING + NODE_H + SWIMLANE_GAP;
      laneIndex++;
    }

    return result;
  }, [nodeStates, dagBlueprint, selectedNodeId]);

  const edges: Edge[] = useMemo(() => {
    const allEdges: { source: string; target: string; dashed?: boolean }[] = [];

    if (dagBlueprint?.edges && dagBlueprint.edges.length > 0) {
      for (const e of dagBlueprint.edges) {
        allEdges.push({ source: e.from_node || e.from || '', target: e.to_node || e.to || '' });
      }
    } else if (dagBlueprint?.nodes && dagBlueprint.nodes.length > 0) {
      for (const node of dagBlueprint.nodes) {
        for (const dep of node.depends_on || []) {
          allEdges.push({ source: dep, target: node.id });
        }
      }
    }

    if (allEdges.length === 0) {
      const ids = Object.keys(nodeStates);
      for (let i = 0; i < ids.length - 1; i++) {
        allEdges.push({ source: ids[i], target: ids[i + 1] });
      }
    }

    if (dagBlueprint?.feedback_edges) {
      for (const fe of dagBlueprint.feedback_edges) {
        allEdges.push({ source: fe.from_node || fe.from || '', target: fe.to_node || fe.to || '', dashed: true });
      }
    }

    return allEdges.map((e, i) => {
      const sourceStatus = nodeStates[e.source];
      const isAnimated = sourceStatus === 'running';
      const isCompleted = sourceStatus === 'completed';
      return {
        id: `e-${e.source}-${e.target}-${i}`,
        source: e.source,
        target: e.target,
        animated: isAnimated,
        style: {
          stroke: isCompleted ? '#22c55e' : isAnimated ? '#3b82f6' : '#94a3b8',
          strokeWidth: isCompleted || isAnimated ? 2.5 : 1.8,
          strokeDasharray: e.dashed ? '6 4' : undefined,
        },
      };
    });
  }, [nodeStates, dagBlueprint]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => { onNodeClick?.(node.id); },
    [onNodeClick],
  );

  return (
    <div style={{ width: '100%', height: '100%', minHeight: '500px' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodeClick={handleNodeClick}
        nodeTypes={NODE_TYPES}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.3}
        maxZoom={2}
      >
        <Background gap={24} size={1} color="#e2e8f0" />
        <Controls showInteractive={false} />
      </ReactFlow>
      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
      `}</style>
    </div>
  );
}