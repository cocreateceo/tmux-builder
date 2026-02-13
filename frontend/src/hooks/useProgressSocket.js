import { useState, useEffect, useRef, useCallback } from 'react';

// Auto-detect WebSocket URL based on environment
const getWsUrl = () => {
  if (typeof window === 'undefined') return 'ws://localhost:8082';
  const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  if (isLocalhost) return 'ws://localhost:8082';
  // Production: use wss:// with same host (CloudFront proxies /ws/ to backend)
  return `wss://${window.location.host}`;
};

const MCP_WS_URL = getWsUrl();
const MAX_RECONNECT_ATTEMPTS = 5;
const MAX_LOG_ENTRIES = 500;

// Message types that should be logged to activity log
const LOGGABLE_TYPES = new Set([
  'ack', 'status', 'working', 'progress', 'found', 'phase',
  'created', 'deployed', 'screenshot', 'test', 'summary', 'done', 'complete', 'error'
]);

/**
 * Format activity message for user-friendly display.
 * Filters out technical AWS details and converts to readable messages.
 */
function formatActivityMessage(msg) {
  const { type, message } = msg;

  // Skip if message contains raw AWS JSON data
  if (message && typeof message === 'string') {
    // Check if it's JSON with AWS details - skip these
    if (message.includes('"s3_bucket"') ||
        message.includes('"cloudfront_id"') ||
        message.includes('"cloudfront_url"') ||
        message.includes('"region"')) {
      return null; // Filter out
    }

    // Check if it starts with { and contains AWS-like patterns
    if (message.trim().startsWith('{') &&
        (message.includes('tmux-') || message.includes('cloudfront.net'))) {
      return null; // Filter out raw JSON
    }
  }

  // Format progress messages
  if (type === 'progress') {
    const value = parseInt(message, 10);
    if (!isNaN(value)) {
      return { ...msg, message: `${value}%` };
    }
  }

  // User-friendly message mappings
  const friendlyMessages = {
    'ack': 'Session acknowledged',
    'done': 'Task completed',
    'complete': 'Task completed',
    'summary': 'Generating summary...',
  };

  if (friendlyMessages[type] && (!message || message === type)) {
    return { ...msg, message: friendlyMessages[type] };
  }

  // Format specific patterns in messages
  if (message && typeof message === 'string') {
    let formatted = message;

    // Convert technical terms to friendly ones
    const replacements = [
      [/creating s3 bucket/i, 'Creating storage bucket...'],
      [/s3 bucket created/i, 'Storage bucket ready'],
      [/creating cloudfront/i, 'Setting up CDN...'],
      [/cloudfront.*created/i, 'CDN configured'],
      [/cloudfront.*ready/i, 'CDN ready'],
      [/uploading.*s3/i, 'Uploading files...'],
      [/files uploaded/i, 'Files uploaded'],
      [/configuring cors/i, 'Configuring access settings...'],
      [/cors configured/i, 'Access settings configured'],
      [/npm install/i, 'Installing dependencies...'],
      [/npm run build/i, 'Building project...'],
      [/vite build/i, 'Compiling code...'],
      [/health check/i, 'Verifying deployment...'],
      [/website.*live/i, 'Website is live!'],
      [/deployment.*complete/i, 'Deployment complete!'],
    ];

    for (const [pattern, replacement] of replacements) {
      if (pattern.test(formatted)) {
        formatted = replacement;
        break;
      }
    }

    return { ...msg, message: formatted };
  }

  return msg;
}

function isValidGuid(guid) {
  return guid && guid !== 'null' && guid !== 'undefined';
}

/**
 * Hook for receiving real-time progress updates from Claude CLI via WebSocket.
 *
 * Architecture:
 * - HTTP API (port 8000): Chat request/response
 * - WebSocket (port 8001): Real-time progress updates via notify.sh
 */
export function useProgressSocket(guid, handlers = {}) {
  const [connected, setConnected] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [phase, setPhase] = useState('idle');
  const [activityLog, setActivityLog] = useState([]);

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const isConnectingRef = useRef(false);
  const handlersRef = useRef(handlers);
  const guidRef = useRef(guid);
  const idCounterRef = useRef(0);

  useEffect(() => { handlersRef.current = handlers; }, [handlers]);
  useEffect(() => { guidRef.current = guid; }, [guid]);

  function normalizeMessage(raw) {
    return {
      type: raw.type || 'unknown',
      message: raw.message || raw.data || '',
      data: raw.data,
      guid: raw.guid,
      timestamp: raw.timestamp || new Date().toISOString(),
    };
  }

  const addToActivityLog = useCallback((msg) => {
    // Format message for user-friendly display
    const formattedMsg = formatActivityMessage(msg);

    // Skip if message was filtered out (e.g., raw AWS JSON)
    if (!formattedMsg) {
      return;
    }

    setActivityLog((prev) => {
      idCounterRef.current += 1;
      const entry = {
        id: `${Date.now()}-${idCounterRef.current}-${Math.random().toString(36).slice(2, 9)}`,
        type: formattedMsg.type,
        message: formattedMsg.message,
        timestamp: formattedMsg.timestamp,
      };
      return [...prev, entry].slice(-MAX_LOG_ENTRIES);
    });
  }, []);

  // Message type handlers - map each type to state updates and handler calls
  const handleMessage = useCallback((rawData) => {
    const data = normalizeMessage(rawData);

    // Call generic onMessage handler for all messages
    handlersRef.current.onMessage?.(data);

    // Add to activity log if applicable
    if (LOGGABLE_TYPES.has(data.type) || !['connected', 'history', 'pong'].includes(data.type)) {
      addToActivityLog(data);
    }

    // Type-specific handling
    const typeHandlers = {
      ack: () => {
        setPhase('processing');
        setStatusMessage('Processing...');
        handlersRef.current.onAck?.(data);
      },
      progress: () => {
        const value = parseInt(data.data, 10) || 0;
        setProgress(Math.min(100, Math.max(0, value)));
        setPhase('processing');
        handlersRef.current.onProgress?.(data);
      },
      status: () => {
        setStatusMessage(data.message);
        setPhase('processing');
        handlersRef.current.onStatus?.(data);
      },
      working: () => {
        setStatusMessage(data.message);
        setPhase('working');
        handlersRef.current.onWorking?.(data);
      },
      found: () => {
        setStatusMessage(`Found: ${data.message}`);
        handlersRef.current.onFound?.(data);
      },
      phase: () => {
        setPhase(data.message || 'processing');
        handlersRef.current.onPhase?.(data);
      },
      created: () => {
        setStatusMessage(`Created: ${data.message}`);
        handlersRef.current.onCreated?.(data);
      },
      deployed: () => {
        setStatusMessage(`Deployed: ${data.message}`);
        setPhase('deployed');
        handlersRef.current.onDeployed?.(data);
      },
      screenshot: () => {
        setStatusMessage(`Screenshot: ${data.message}`);
        handlersRef.current.onScreenshot?.(data);
      },
      test: () => {
        setStatusMessage(`Test: ${data.message}`);
        handlersRef.current.onTest?.(data);
      },
      summary: () => {
        setStatusMessage('Task completed');
        setPhase('complete');
        setProgress(100);
        handlersRef.current.onSummary?.(data);
      },
      response: () => {
        setPhase('complete');
        setProgress(100);
        handlersRef.current.onResponse?.(data);
      },
      done: () => {
        setPhase('complete');
        setProgress(100);
        setStatusMessage('Complete');
        handlersRef.current.onComplete?.(data);
      },
      complete: () => typeHandlers.done(),
      completed: () => typeHandlers.done(),
      error: () => {
        setPhase('error');
        setStatusMessage(data.message || 'An error occurred');
        handlersRef.current.onError?.(data);
      },
      history: () => {
        if (rawData.messages?.length) {
          rawData.messages.forEach(msg => addToActivityLog(normalizeMessage(msg)));
        }
        handlersRef.current.onHistory?.(rawData);
      },
      tool_log: () => handlersRef.current.onToolLog?.(data),
      connected: () => {},
    };

    const handler = typeHandlers[data.type];
    if (handler) {
      handler();
    } else {
      setStatusMessage(data.message);
      handlersRef.current.onCustom?.(data);
    }
  }, [addToActivityLog]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    const currentGuid = guidRef.current;
    if (!isValidGuid(currentGuid)) return;

    // Prevent duplicate connections
    if (isConnectingRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (wsRef.current?.readyState === WebSocket.CONNECTING) return;

    isConnectingRef.current = true;

    // Clean up existing connection
    if (wsRef.current) {
      try { wsRef.current.close(1000, 'Reconnecting'); } catch (e) {}
      wsRef.current = null;
    }

    console.log(`[MCP-WS] Connecting to ${MCP_WS_URL}/ws/${currentGuid}`);
    const ws = new WebSocket(`${MCP_WS_URL}/ws/${currentGuid}`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[MCP-WS] Connected');
      isConnectingRef.current = false;
      setConnected(true);
      reconnectAttempts.current = 0;
      handlersRef.current.onConnect?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('[MCP-WS] Received:', data.type, data.message || data.data || '');
        handleMessage(data);
      } catch (err) {
        console.error('[MCP-WS] Failed to parse message:', err);
      }
    };

    ws.onclose = (event) => {
      console.log(`[MCP-WS] Disconnected (code: ${event.code})`);
      isConnectingRef.current = false;
      setConnected(false);

      if (wsRef.current === ws) {
        handlersRef.current.onDisconnect?.();
        wsRef.current = null;

        // Don't reconnect for certain close codes
        // 1000: Normal close (intentional disconnect)
        // 1011: Server error indicating invalid/deleted session
        // Note: 1008 (Policy Violation) could be transient, so we allow retry
        const noReconnectCodes = [1000, 1011];
        if (noReconnectCodes.includes(event.code)) {
          console.log(`[MCP-WS] Not reconnecting (code ${event.code} indicates permanent close)`);
          return;
        }

        // Auto-reconnect with exponential backoff for transient errors
        if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 10000);
          console.log(`[MCP-WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current + 1}/${MAX_RECONNECT_ATTEMPTS})`);
          if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++;
            connect();
          }, delay);
        }
      }
    };

    ws.onerror = (err) => {
      console.error('[MCP-WS] Error:', err);
      isConnectingRef.current = false;
    };
  }, [handleMessage]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      try { wsRef.current.close(1000, 'User disconnect'); } catch (e) {}
      wsRef.current = null;
    }
    isConnectingRef.current = false;
    setConnected(false);
  }, []);

  const reconnect = useCallback(() => {
    reconnectAttempts.current = 0;
    disconnect();
    setTimeout(connect, 100);
  }, [connect, disconnect]);

  const resetProgress = useCallback(() => {
    setProgress(0);
    setStatusMessage('');
    setPhase('idle');
  }, []);

  const clearActivityLog = useCallback(() => setActivityLog([]), []);

  // Connect when guid changes
  useEffect(() => {
    if (!isValidGuid(guid)) return;

    const timer = setTimeout(connect, 200);
    return () => {
      clearTimeout(timer);
      disconnect();
    };
  }, [guid, connect, disconnect]);

  return {
    connected,
    progress,
    statusMessage,
    phase,
    activityLog,
    reconnect,
    disconnect,
    resetProgress,
    clearActivityLog,
  };
}

export default useProgressSocket;
