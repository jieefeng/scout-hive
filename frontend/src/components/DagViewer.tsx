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

interface DagViewerProps {
  nodeStates: Record<string, string>;
  dagBlueprint?: DagBlueprint | null;
  onNodeClick?: (nodeId: string) => void;
  selectedNodeId?: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  pending: '#94a3b8', running: '#3b82f6', completed: '#22c55e',
  failed: '#ef4444', skipped: '#f59e0b',
};

const STATUS_BG: Record<string, string> = {
  pending: '#f8fafc', running: '#eff6ff', completed: '#f0fdf4',
  failed: '#fef2f2', skipped: '#fffbeb',
};

const STATUS_ICONS: Record<string, string> = {
  pending: '⏳', running: '🔄', completed: '✅', failed: '❌', skipped: '⏭️',
};

const NODE_W = 170;
const NODE_H = 88;
const COL_GAP = 64;
const ROW_GAP = 56;

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

  const agentMap: Record<string, string> = { c: "Collector", a: "Analyst", w: "Writer", r: "Reviewer" };
  const prefix = label.split("_")[0];
  const agentName = agentMap[prefix] || agent || label;

  const parts = label.split("_");
  const competitorName = competitor || (parts.length >= 2 ? parts[1] : "");
  const dimensionName = dimension || (parts.length >= 3 ? parts.slice(2).join("_") : "");

  const accent = AGENT_ACCENT[agentName] || '#64748b';

  return (
    <>
      <Handle type="target" position={Position.Top} style={{ visibility: 'hidden' }} />
      <div style={{ textAlign: 'center', lineHeight: 1.2 }}>
        <div style={{ fontSize: '1.3rem', marginBottom: '3px' }}>{(status && STATUS_ICONS[status]) || '⏳'}</div>
        <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#1e293b', marginBottom: '3px', whiteSpace: 'nowrap' }}>
          {AGENT_LABELS[agentName] || agentName}
        </div>
        {dimensionName && (
          <div style={{
            fontSize: '0.6rem', color: accent, maxWidth: '150px',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', margin: '0 auto',
            fontWeight: 600,
          }}>{dimensionName}</div>
        )}
        {competitorName && (
          <div style={{
            fontSize: '0.55rem', color: '#94a3b8', maxWidth: '150px',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', margin: '0 auto',
          }}>{competitorName}</div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ visibility: 'hidden' }} />
    </>
  );
}

const NODE_TYPES = { default: DagNodeComponent };

export default function DagViewer({ nodeStates, dagBlueprint, onNodeClick, selectedNodeId }: DagViewerProps) {
  const nodes: Node[] = useMemo(() => {
    const blueprintNodes = dagBlueprint?.nodes || [];
    const allIds = blueprintNodes.length > 0
      ? blueprintNodes.map(n => n.id)
      : Object.keys(nodeStates);

    const cols = Math.max(1, Math.ceil(Math.sqrt(allIds.length)));

    return allIds.map((id, index) => {
      const status = nodeStates[id] || 'pending';
      const isSelected = id === selectedNodeId;

      // Extract agent and dimension from node ID or dagBlueprint
      let agentName = '';
      let dimensionName = '';
      if (dagBlueprint?.nodes) {
        const node = dagBlueprint.nodes.find(n => n.id === id);
        if (node) {
          agentName = node.agent || '';
          dimensionName = node.params?.dimension || '';
        }
      }
      if (!agentName && !dimensionName) {
        // Fallback: parse from ID like c_飞书_功能对比
        const prefix = id.split('_')[0];
        const agentMap: Record<string, string> = { c: 'Collector', a: 'Analyst', w: 'Writer', r: 'Reviewer' };
        agentName = agentMap[prefix] || '';
        const parts = id.split('_');
        dimensionName = parts.length >= 3 ? parts.slice(2).join('_') : '';
      }

      return {
        id,
        type: 'default',
        position: {
          x: (NODE_W + COL_GAP) * (index % cols),
          y: (NODE_H + ROW_GAP) * Math.floor(index / cols),
        },
        data: { label: id, agent: agentName, dimension: dimensionName, status: nodeStates[id] || 'pending' },
        style: {
          width: NODE_W,
          height: NODE_H,
          border: `2px solid ${isSelected ? '#1d4ed8' : STATUS_COLORS[status] || '#94a3b8'}`,
          borderRadius: '14px',
          padding: '8px 10px',
          background: isSelected ? '#dbeafe' : (STATUS_BG[status] || '#f8fafc'),
          boxShadow: isSelected
            ? '0 0 0 3px rgba(59,130,246,0.3), 0 4px 16px rgba(0,0,0,0.12)'
            : status === 'running'
              ? '0 0 16px rgba(59,130,246,0.25), 0 2px 8px rgba(0,0,0,0.06)'
              : '0 2px 8px rgba(0,0,0,0.05)',
          animation: status === 'running' ? 'dag-glow 2s ease-in-out infinite' : 'none',
          cursor: 'pointer',
          transition: 'box-shadow 0.2s, border-color 0.2s, transform 0.15s',
        },
      };
    });
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
        @keyframes dag-glow {
          0%, 100% { opacity: 1; box-shadow: 0 0 16px rgba(59,130,246,0.25), 0 2px 8px rgba(0,0,0,0.06); }
          50% { opacity: 0.85; box-shadow: 0 0 24px rgba(59,130,246,0.4), 0 4px 12px rgba(0,0,0,0.08); }
        }
      `}</style>
    </div>
  );
}