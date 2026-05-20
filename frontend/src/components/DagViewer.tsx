import { useCallback, useMemo } from 'react';
import { ReactFlow, Background, Controls, type Node, type Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

interface DagViewerProps {
  nodeStates: Record<string, string>;
  onNodeClick?: (nodeId: string) => void;
}

const STATUS_COLORS: Record<string, string> = {
  pending: '#9e9e9e', running: '#2196f3', completed: '#4caf50',
  failed: '#f44336', skipped: '#ff9800',
};

const STATUS_ICONS: Record<string, string> = {
  pending: '⏳', running: '🔄', completed: '✅', failed: '❌', skipped: '⏭️',
};

export default function DagViewer({ nodeStates, onNodeClick }: DagViewerProps) {
  const nodes: Node[] = useMemo(() => {
    return Object.entries(nodeStates).map(([id, status], index) => ({
      id,
      position: { x: 250 * (index % 3), y: 100 * Math.floor(index / 3) },
      data: {
        label: (
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '1.5rem' }}>{STATUS_ICONS[status] || '⏳'}</div>
            <div style={{ fontSize: '0.75rem' }}>{id}</div>
          </div>
        ),
      },
      style: {
        border: `2px solid ${STATUS_COLORS[status] || '#9e9e9e'}`,
        borderRadius: '8px', padding: '10px',
        background: status === 'running' ? '#e3f2fd' : '#fff',
        animation: status === 'running' ? 'pulse 2s infinite' : 'none',
      },
    }));
  }, [nodeStates]);

  const edges: Edge[] = useMemo(() => {
    const edgeList: Edge[] = [];
    const ids = Object.keys(nodeStates);
    for (let i = 0; i < ids.length - 1; i++) {
      edgeList.push({
        id: `${ids[i]}-${ids[i + 1]}`, source: ids[i], target: ids[i + 1],
        animated: nodeStates[ids[i]] === 'running',
      });
    }
    return edgeList;
  }, [nodeStates]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => { onNodeClick?.(node.id); },
    [onNodeClick],
  );

  return (
    <div style={{ width: '100%', height: '400px' }}>
      <ReactFlow nodes={nodes} edges={edges} onNodeClick={handleNodeClick} fitView>
        <Background />
        <Controls />
      </ReactFlow>
      <style>{`@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }`}</style>
    </div>
  );
}
