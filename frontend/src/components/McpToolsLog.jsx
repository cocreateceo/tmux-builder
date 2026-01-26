import { useEffect, useRef } from 'react';

function McpToolsLog({ logs, connected }) {
  const logEndRef = useRef(null);

  // Auto-scroll to bottom on new logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const formatTimestamp = (ts) => {
    const date = new Date(ts);
    return date.toLocaleTimeString('en-US', { hour12: false });
  };

  const getToolColor = (tool) => {
    const colors = {
      notify_ack: 'text-green-600',
      send_progress: 'text-blue-600',
      send_status: 'text-purple-600',
      send_response: 'text-orange-600',
      notify_complete: 'text-green-700 font-bold',
      notify_error: 'text-red-600 font-bold',
    };
    return colors[tool] || 'text-gray-600';
  };

  const formatArguments = (tool, args) => {
    if (!args) return '';
    switch (tool) {
      case 'notify_ack':
        return '';
      case 'send_progress':
        return `${args.percent}%`;
      case 'send_status':
        return `"${args.message}" [${args.phase || 'working'}]`;
      case 'send_response':
        const preview = args.content?.substring(0, 50) || '';
        return `"${preview}${args.content?.length > 50 ? '...' : ''}"`;
      case 'notify_complete':
        return args.success ? 'SUCCESS' : 'FAILED';
      case 'notify_error':
        return `"${args.error}"`;
      default:
        return JSON.stringify(args);
    }
  };

  return (
    <div className="h-full flex flex-col bg-gray-900 text-gray-100 font-mono text-sm">
      {/* Header */}
      <div className="p-3 border-b border-gray-700 flex items-center justify-between">
        <h3 className="font-semibold text-gray-300">MCP Tools Log</h3>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`}></span>
          <span className="text-xs text-gray-500">Channel 2</span>
        </div>
      </div>

      {/* Log entries */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        {logs.length === 0 ? (
          <div className="text-gray-500 text-center py-8">
            Waiting for MCP tool calls...
          </div>
        ) : (
          logs.map((log, index) => (
            <div key={index} className="flex gap-2">
              <span className="text-gray-500 flex-shrink-0">
                {formatTimestamp(log.timestamp)}
              </span>
              <span className={getToolColor(log.tool)}>
                {log.tool}
              </span>
              <span className="text-gray-400">
                {formatArguments(log.tool, log.args)}
              </span>
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>

      {/* Progress bar */}
      {logs.some(l => l.tool === 'send_progress') && !logs.some(l => l.tool === 'notify_complete') && (
        <div className="p-3 border-t border-gray-700">
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{
                width: `${logs.filter(l => l.tool === 'send_progress').pop()?.args?.percent || 0}%`
              }}
            ></div>
          </div>
        </div>
      )}
    </div>
  );
}

export default McpToolsLog;
