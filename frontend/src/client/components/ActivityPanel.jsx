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
  onToggleCollapse
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
      <div className="w-12 flex flex-col items-center py-4 border-l
        dark:bg-[#12121a] dark:border-gray-800 bg-gray-50 border-gray-200">
        <button
          onClick={onToggleCollapse}
          className="p-2 rounded-lg dark:hover:bg-gray-800 hover:bg-gray-100
            dark:text-gray-400 text-gray-500"
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
                stroke="currentColor"
                strokeWidth="2"
                className="dark:text-gray-700 text-gray-200"
              />
              <circle
                cx="12"
                cy="12"
                r="10"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeDasharray={`${progress * 0.628} 62.8`}
                className="text-indigo-500"
              />
            </svg>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="w-80 flex flex-col border-l
      dark:bg-[#12121a] dark:border-gray-800 bg-gray-50 border-gray-200">

      {/* Header */}
      <div className="h-14 px-4 flex items-center justify-between border-b
        dark:border-gray-800 border-gray-200">
        <div className="flex items-center gap-2">
          <span className="font-semibold dark:text-white text-gray-900">Activity</span>
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
        </div>
        <button
          onClick={onToggleCollapse}
          className="p-2 rounded-lg dark:hover:bg-gray-800 hover:bg-gray-100
            dark:text-gray-400 text-gray-500"
          title="Collapse"
        >
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>

      {/* Progress bar */}
      {(progress > 0 || statusMessage) && (
        <div className="px-4 py-3 border-b dark:border-gray-800 border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm dark:text-gray-400 text-gray-600">Progress</span>
            <span className="text-sm font-medium dark:text-white text-gray-900">{progress}%</span>
          </div>
          <div className="h-2 rounded-full dark:bg-gray-700 bg-gray-200 overflow-hidden">
            <div
              className="h-full bg-indigo-500 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          {statusMessage && (
            <p className="mt-2 text-xs dark:text-gray-500 text-gray-400 truncate">
              {statusMessage}
            </p>
          )}
        </div>
      )}

      {/* Logs */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {logs.length === 0 ? (
          <div className="text-center py-8 dark:text-gray-500 text-gray-400 text-sm">
            No activity yet
          </div>
        ) : (
          logs.map((log, index) => (
            <div
              key={index}
              className="flex gap-2 text-xs"
            >
              <span className="dark:text-gray-600 text-gray-400 font-mono whitespace-nowrap">
                {formatTime(log.timestamp)}
              </span>
              <div className="flex items-start gap-1.5 min-w-0">
                {getEventIcon(log.type)}
                <span className="dark:text-gray-300 text-gray-600 break-words">
                  {log.message || log.type}
                </span>
              </div>
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>

      {/* Auto-scroll toggle */}
      <div className="px-4 py-2 border-t dark:border-gray-800 border-gray-200">
        <label className="flex items-center gap-2 text-xs cursor-pointer">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="rounded border-gray-300 dark:border-gray-600
              text-indigo-500 focus:ring-indigo-500"
          />
          <span className="dark:text-gray-400 text-gray-500">Auto-scroll</span>
        </label>
      </div>
    </div>
  );
}
