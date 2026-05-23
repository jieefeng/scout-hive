import { useCallback, useMemo } from 'react';
import { ReactFlow, Background, Controls, type Node, type Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

interface DagEdge { from_node?: string; from?: string; to_node?: string; to?: string; }
interface DagNode { id: string; agent: string; action: string; depends_on?: string[]; }
interface DagBlueprint { nodes?: DagNode[]; edges?: DagEdge[]; feedback_edges?: DagEdge[]; }

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

const NODE_W = 200;
const NODE_H = 90;
const COL_GAP = 80;
const ROW_GAP = 60;

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

      return {
        id,
        position: {
          x: (NODE_W + COL_GAP) * (index % cols),
          y: (NODE_H + ROW_GAP) * Math.floor(index / cols),
        },
        data: { label: id },
        width: NODE_W,
        height: NODE_H,
        style: {
          width: NODE_W,
          height: NODE_H,
          border: `2px solid ${isSelected ? '#1d4ed8' : STATUS_COLORS[status] || '#94a3b8'}`,
          borderRadius: '12px',
          padding: '12px 14px',
          background: isSelected ? '#dbeafe' : (STATUS_BG[status] || '#f8fafc'),
          boxShadow: isSelected
            ? '0 0 0 3px rgba(59,130,246,0.3), 0 4px 12px rgba(0,0,0,0.1)'
            : status === 'running'
              ? '0 0 12px rgba(59,130,246,0.3), 0 2px 8px rgba(0,0,0,0.06)'
              : '0 2px 8px rgba(0,0,0,0.06)',
          animation: status === 'running' ? 'dag-pulse 2s ease-in-out infinite' : 'none',
          cursor: 'pointer',
          transition: 'box-shadow 0.2s, border-color 0.2s',
        },
      };
    });
  }, [nodeStates, dagBlueprint, selectedNodeId]);

  const edges: Edge[] = useMemo(() => {
    const allEdges: { source: string; target: string; dashed?: boolean }[] = [];

    // Priority 1: explicit edges from blueprint
    if (dagBlueprint?.edges && dagBlueprint.edges.length > 0) {
      for (const e of dagBlueprint.edges) {
        allEdges.push({ source: e.from_node || e.from || '', target: e.to_node || e.to || '' });
      }
    } else if (dagBlueprint?.nodes && dagBlueprint.nodes.length > 0) {
      // Priority 2: derive edges from depends_on
      for (const node of dagBlueprint.nodes) {
        for (const dep of node.depends_on || []) {
          allEdges.push({ source: dep, target: node.id });
        }
      }
    }

    // Priority 3: sequential fallback from nodeStates
    if (allEdges.length === 0) {
      const ids = Object.keys(nodeStates);
      for (let i = 0; i < ids.length - 1; i++) {
        allEdges.push({ source: ids[i], target: ids[i + 1] });
      }
    }

    // Add feedback edges (dashed)
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
          stroke: isCompleted ? '#22c55e' : isAnimated ? '#3b82f6' : '#cbd5e1',
          strokeWidth: isCompleted || isAnimated ? 2.5 : 1.5,
          strokeDasharray: e.dashed ? '5 5' : undefined,
        },
      };
    });
  }, [nodeStates, dagBlueprint]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => { onNodeClick?.(node.id); },
    [onNodeClick],
  );

  // Custom node rendering
  const nodeTypes = useMemo(() => ({
    default: ({ data }: { data: { label: string } }) => {
      const nodeId = data.label;
      const status = nodeStates[nodeId] || 'pending';
      const bpNode = dagBlueprint?.nodes?.find(n => n.id === nodeId);
      return (
        <div style={{ textAlign: 'center', lineHeight: 1.3 }}>
          <div style={{ fontSize: '1.4rem', marginBottom: '2px' }}>{STATUS_ICONS[status] || '⏳'}</div>
          <div style={{ fontSize: '0.7rem', fontWeight: 600, color: '#1e293b', wordBreak: 'break-all' }}>{nodeId}</div>
          {bpNode && <div style={{ fontSize: '0.6rem', color: '#64748b', marginTop: '2px' }}>{bpNode.agent}</div>}
        </div>
      );
    },
  }), [nodeStates, dagBlueprint]);

  console.log('[DagViewer] FINAL nodes:', nodes.map(n => ({ id: n.id, w: n.width, h: n.height, x: n.position.x, y: n.position.y })));
  console.log('[DagViewer] FINAL edges:', edges.map(e => ({ id: e.id, src: e.source, tgt: e.target })));
  console.log('[DagViewer] dagBlueprint:', dagBlueprint ? { nodes: dagBlueprint.nodes?.length, edges: dagBlueprint.edges?.length } : 'null');

  return (
    <div style={{ width: '100%', height: '100%', minHeight: '500px' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodeClick={handleNodeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.3}
        maxZoom={2}
        defaultEdgeOptions={{ type: 'default' }}
      >
        <Background gap={20} size={1} color="#e2e8f0" />
        <Controls showInteractive={false} />
      </ReactFlow>
      <style>{`@keyframes dag-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.65; } }`}</style>
    </div>
  );
}
