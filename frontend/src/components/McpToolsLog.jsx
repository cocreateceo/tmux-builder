import { useEffect, useRef, useMemo } from 'react';

/**
 * Activity Log component for displaying real-time progress updates from Claude CLI.
 *
 * Supports message format from notify.sh:
 * { type: 'status', message: 'Working on...', timestamp: '...' }
 */
function McpToolsLog({ logs, connected, progress }) {
  const logEndRef = useRef(null);

  // Auto-scroll to bottom on new logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Calculate progress from logs if not passed as prop
  const latestProgress = useMemo(() => {
    if (progress !== undefined && progress !== null) return progress;
    const progressLogs = logs.filter(l => l.type === 'progress');
    if (progressLogs.length > 0) {
      const lastProgress = progressLogs[progressLogs.length - 1];
      return parseInt(lastProgress.message || lastProgress.data || '0', 10);
    }
    return null;
  }, [logs, progress]);

  const isComplete = useMemo(() =>
    logs.some(l => ['done', 'complete', 'completed'].includes(l.type)),
    [logs]
  );

  const formatTimestamp = (ts) => {
    if (!ts) return '';
    const date = new Date(ts);
    return date.toLocaleTimeString('en-US', { hour12: false });
  };

  const getTypeColor = (type) => {
    const colors = {
      ack: 'text-green-500',
      progress: 'text-blue-500',
      status: 'text-purple-400',
      working: 'text-yellow-400',
      found: 'text-cyan-400',
      phase: 'text-indigo-400',
      created: 'text-emerald-400',
      deployed: 'text-green-400 font-bold',
      screenshot: 'text-pink-400',
      test: 'text-orange-400',
      done: 'text-green-500 font-bold',
      complete: 'text-green-500 font-bold',
      completed: 'text-green-500 font-bold',
      error: 'text-red-500 font-bold',
      // Legacy MCP tool types
      notify_ack: 'text-green-500',
      send_progress: 'text-blue-500',
      send_status: 'text-purple-400',
      send_response: 'text-orange-400',
      notify_complete: 'text-green-500 font-bold',
      notify_error: 'text-red-500 font-bold',
    };
    return colors[type] || 'text-gray-400';
  };

  const getTypeIcon = (type) => {
    const icons = {
      ack: '✓',
      progress: '📊',
      status: '💬',
      working: '⚙️',
      found: '🔍',
      phase: '📋',
      created: '📄',
      deployed: '🚀',
      screenshot: '📸',
      test: '🧪',
      done: '✅',
      complete: '✅',
      completed: '✅',
      error: '❌',
    };
    return icons[type] || '•';
  };

  const formatMessage = (log) => {
    // Handle both new format (type/message) and legacy format (tool/args)
    if (log.tool) {
      // Legacy MCP format
      const { tool, args } = log;
      if (!args) return '';
      switch (tool) {
        case 'notify_ack': return 'Acknowledged';
        case 'send_progress': return `${args.percent}%`;
        case 'send_status': return `${args.message}${args.phase ? ` [${args.phase}]` : ''}`;
        case 'send_response': {
          const preview = args.content?.substring(0, 50) || '';
          return `"${preview}${args.content?.length > 50 ? '...' : ''}"`;
        }
        case 'notify_complete': return args.success ? 'Task completed' : 'Task failed';
        case 'notify_error': return args.error;
        default: return JSON.stringify(args);
      }
    }

    // New notify.sh format
    const { type, message } = log;
    if (!message && type === 'ack') return 'Acknowledged';
    if (!message && (type === 'done' || type === 'complete')) return 'Task completed';
    return message || '';
  };

  const getDisplayType = (log) => {
    // Handle both formats
    return log.type || log.tool || 'unknown';
  };

  return (
    <div className="h-full flex flex-col bg-gray-900 text-gray-100 font-mono text-sm">
      {/* Header */}
      <div className="p-3 border-b border-gray-700 flex items-center justify-between">
        <h3 className="font-semibold text-gray-300">Activity Log</h3>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`}></span>
          <span className="text-xs text-gray-500">{connected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </div>

      {/* Log entries */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        {logs.length === 0 ? (
          <div className="text-gray-500 text-center py-8">
            Waiting for activity...
          </div>
        ) : (
          logs.map((log, index) => {
            const displayType = getDisplayType(log);
            return (
              <div key={log.id || `${log.timestamp}-${displayType}-${index}`} className="flex gap-2 py-0.5">
                <span className="text-gray-600 flex-shrink-0 w-20">
                  {formatTimestamp(log.timestamp)}
                </span>
                <span className="flex-shrink-0 w-5 text-center">
                  {getTypeIcon(displayType)}
                </span>
                <span className={`flex-shrink-0 w-24 ${getTypeColor(displayType)}`}>
                  {displayType}
                </span>
                <span className="text-gray-300 break-all">
                  {formatMessage(log)}
                </span>
              </div>
            );
          })
        )}
        <div ref={logEndRef} />
      </div>

      {/* Progress bar */}
      {latestProgress !== null && latestProgress > 0 && !isComplete && (
        <div className="p-3 border-t border-gray-700">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-gray-400">Progress</span>
            <span className="text-xs text-blue-400">{latestProgress}%</span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${latestProgress}%` }}
            ></div>
          </div>
        </div>
      )}

      {/* Completion indicator */}
      {isComplete && (
        <div className="p-3 border-t border-gray-700 bg-green-900/20">
          <div className="flex items-center gap-2 text-green-400">
            <span>✅</span>
            <span className="text-sm font-medium">Task Complete</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default McpToolsLog;
