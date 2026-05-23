import type { TaskSummary } from '../types';

interface ReportViewerProps {
  task: TaskSummary | null;
  onFindingClick?: (findingId: string, sourceId: string) => void;
}

export default function ReportViewer({ task }: ReportViewerProps) {
  if (!task?.report_html) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>
        报告生成中...
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* 左侧：报告主体 */}
      <div
        style={{ flex: 1, overflow: 'auto', padding: '1.5rem' }}
        dangerouslySetInnerHTML={{ __html: task.report_html }}
      />

      {/* 右侧：溯源面板（点击结论时触发） */}
      <div
        id="source-panel"
        style={{
          width: 0,
          overflow: 'hidden',
          transition: 'width 0.3s',
          background: '#fffde7',
          borderLeft: '1px solid #e0e0e0',
        }}
      />
    </div>
  );
}