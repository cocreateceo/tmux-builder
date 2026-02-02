import { useState, useEffect, useRef } from 'react';
import {
  ChevronRight,
  ChevronLeft,
  CheckCircle,
  AlertCircle,
  Loader,
  FileText,
  Rocket
} from 'lucide-react';

function getEventIcon(type) {
  switch (type) {
    case 'ack':
      return <CheckCircle className="w-3.5 h-3.5 text-green-500" />;
    case 'error':
      return <AlertCircle className="w-3.5 h-3.5 text-red-500" />;
    case 'file_created':
    case 'file_modified':
      return <FileText className="w-3.5 h-3.5 text-blue-500" />;
    case 'deployed':
      return <Rocket className="w-3.5 h-3.5 text-green-500" />;
    case 'done':
    case 'summary':
      return <CheckCircle className="w-3.5 h-3.5 text-green-500" />;
    default:
      return <Loader className="w-3.5 h-3.5 text-yellow-500 animate-spin" />;
  }
}

function formatTime(timestamp) {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

export function ActivityPanel({
  logs = [],
  progress = 0,
  statusMessage = '',
  connected = false,
  collapsed = false,
  onToggleCollapse,
  width = 400
}) {
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll) {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  if (collapsed) {
    return (
      <div
        className="w-12 flex flex-col items-center py-4 border-l"
        style={{ background: 'var(--bg-primary)', borderColor: 'var(--border-color)' }}
      >
        <button
          onClick={onToggleCollapse}
          className="p-2 rounded-lg hover:opacity-80"
          style={{ color: 'var(--text-muted)' }}
          title="Expand activity log"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>

        {/* Mini progress indicator */}
        {progress > 0 && progress < 100 && (
          <div className="mt-4 w-6 h-6 relative">
            <svg className="w-6 h-6 -rotate-90">
              <circle
                cx="12"
                cy="12"
                r="10"
                fill="none"
                stroke="var(--bg-secondary)"
                strokeWidth="2"
              />
              <circle
                cx="12"
                cy="12"
                r="10"
                fill="none"
                stroke="var(--primary)"
                strokeWidth="2"
                strokeDasharray={`${progress * 0.628} 62.8`}
              />
            </svg>
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      className="flex flex-col border-l"
      style={{ width: `${width}px`, background: 'var(--bg-primary)', borderColor: 'var(--border-color)' }}
    >

      {/* Header */}
      <div
        className="h-14 px-4 flex items-center justify-between border-b"
        style={{ borderColor: 'var(--border-color)' }}
      >
        <div className="flex items-center gap-2">
          <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>Activity</span>
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
        </div>
        <button
          onClick={onToggleCollapse}
          className="p-2 rounded-lg hover:opacity-80"
          style={{ color: 'var(--text-muted)' }}
          title="Collapse"
        >
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>

      {/* Progress bar */}
      {(progress > 0 || statusMessage) && (
        <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border-color)' }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm" style={{ color: 'var(--text-muted)' }}>Progress</span>
            <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{progress}%</span>
          </div>
          <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--bg-secondary)' }}>
            <div
              className="h-full rounded-full transition-all duration-300"
              style={{ width: `${progress}%`, background: 'var(--primary)' }}
            />
          </div>
          {statusMessage && (
            <p className="mt-2 text-xs truncate" style={{ color: 'var(--text-muted)' }}>
              {statusMessage}
            </p>
          )}
        </div>
      )}

      {/* Logs */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {logs.length === 0 ? (
          <div className="text-center py-8 text-sm" style={{ color: 'var(--text-muted)' }}>
            No activity yet
          </div>
        ) : (
          logs.map((log, index) => (
            <div
              key={index}
              className="flex gap-2 text-xs"
            >
              <span className="font-mono whitespace-nowrap" style={{ color: 'var(--text-muted)' }}>
                {formatTime(log.timestamp)}
              </span>
              <div className="flex items-start gap-1.5 min-w-0">
                {getEventIcon(log.type)}
                <span className="break-words" style={{ color: 'var(--text-secondary)' }}>
                  {log.message || log.type}
                </span>
              </div>
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>

      {/* Auto-scroll toggle */}
      <div className="px-4 py-2 border-t" style={{ borderColor: 'var(--border-color)' }}>
        <label className="flex items-center gap-2 text-xs cursor-pointer">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="rounded"
            style={{ accentColor: 'var(--primary)' }}
          />
          <span style={{ color: 'var(--text-muted)' }}>Auto-scroll</span>
        </label>
      </div>
    </div>
  );
}
