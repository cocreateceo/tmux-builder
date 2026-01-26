import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * MCP Progress WebSocket URL (Channel 2)
 * Connects to the MCP server for real-time progress updates from Claude CLI
 */
const MCP_WS_URL = 'ws://localhost:8001';

/**
 * Custom hook for receiving real-time progress updates from Claude CLI via MCP WebSocket.
 *
 * Dual-channel architecture:
 * - Channel 1 (useWebSocket): UI <-> Backend (chat request/response on port 8000)
 * - Channel 2 (useProgressSocket): UI <-> MCP Server (real-time progress on port 8001)
 *
 * Message types from MCP server:
 * - ack: Claude acknowledged the prompt
 * - progress: Progress update with percentage
 * - status: Status message update
 * - response: Final response content
 * - complete: Task completed
 * - error: Error occurred
 *
 * @param {string} guid - Session GUID to subscribe to
 * @param {object} handlers - Event handlers
 * @returns {object} - { connected, progress, statusMessage, phase, reconnect, resetProgress }
 */
export function useProgressSocket(guid, handlers = {}) {
  const [connected, setConnected] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [phase, setPhase] = useState('idle');

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const isConnectingRef = useRef(false);
  const handlersRef = useRef(handlers);
  const guidRef = useRef(guid);

  const maxReconnectAttempts = 5;

  // Keep refs updated
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    guidRef.current = guid;
  }, [guid]);

  // Connect to MCP WebSocket
  const connect = useCallback(() => {
    const currentGuid = guidRef.current;

    // More defensive check - handle null, undefined, empty string, and string "null"/"undefined"
    if (!currentGuid || currentGuid === 'null' || currentGuid === 'undefined') {
      console.log('[MCP-WS] No valid GUID provided, skipping connection');
      return;
    }

    if (isConnectingRef.current) {
      console.log('[MCP-WS] Already connecting, skipping');
      return;
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      console.log('[MCP-WS] Already connected');
      return;
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING) {
      console.log('[MCP-WS] Connection in progress, skipping');
      return;
    }

    isConnectingRef.current = true;

    // Clean up existing connection
    if (wsRef.current) {
      try {
        wsRef.current.close(1000, 'Reconnecting');
      } catch (e) {
        // Ignore
      }
      wsRef.current = null;
    }

    // Connect with guid in URL path
    const wsUrl = `${MCP_WS_URL}/ws/${currentGuid}`;
    console.log(`[MCP-WS] Connecting to ${wsUrl}...`);

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[MCP-WS] Connected to MCP progress server');
      isConnectingRef.current = false;
      setConnected(true);
      reconnectAttempts.current = 0;
      handlersRef.current.onConnect?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('[MCP-WS] Received:', data.type, data);

        switch (data.type) {
          case 'ack':
            setPhase('processing');
            setStatusMessage('Processing...');
            handlersRef.current.onAck?.(data);
            break;

          case 'progress':
            setProgress(data.progress || 0);
            setPhase(data.phase || 'processing');
            if (data.message) {
              setStatusMessage(data.message);
            }
            handlersRef.current.onProgress?.(data);
            break;

          case 'status':
            setStatusMessage(data.message || '');
            setPhase(data.phase || 'processing');
            handlersRef.current.onStatus?.(data);
            break;

          case 'response':
            setPhase('complete');
            setProgress(100);
            handlersRef.current.onResponse?.(data);
            break;

          case 'complete':
            setPhase('complete');
            setProgress(100);
            setStatusMessage('Complete');
            handlersRef.current.onComplete?.(data);
            break;

          case 'error':
            setPhase('error');
            setStatusMessage(data.error || data.message || 'An error occurred');
            handlersRef.current.onError?.(data);
            break;

          case 'connected':
            console.log('[MCP-WS] Connection confirmed for GUID:', data.guid);
            break;

          case 'tool_log':
            handlersRef.current.onToolLog?.(data);
            break;

          default:
            console.log('[MCP-WS] Unknown message type:', data.type);
        }
      } catch (err) {
        console.error('[MCP-WS] Failed to parse message:', err);
      }
    };

    ws.onclose = (event) => {
      console.log('[MCP-WS] Disconnected:', event.code, event.reason);
      isConnectingRef.current = false;
      setConnected(false);

      if (wsRef.current === ws) {
        handlersRef.current.onDisconnect?.();
        wsRef.current = null;

        // Auto-reconnect with exponential backoff
        if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 10000);
          console.log(`[MCP-WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current + 1}/${maxReconnectAttempts})`);

          if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
          }

          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++;
            connect();
          }, delay);
        }
      }
    };

    ws.onerror = (error) => {
      console.error('[MCP-WS] Error:', error);
      isConnectingRef.current = false;
    };
  }, []);

  // Disconnect
  const disconnect = useCallback(() => {
    console.log('[MCP-WS] Disconnecting...');

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      try {
        wsRef.current.close(1000, 'User disconnect');
      } catch (e) {
        // Ignore
      }
      wsRef.current = null;
    }

    isConnectingRef.current = false;
    setConnected(false);
  }, []);

  // Manual reconnect
  const reconnect = useCallback(() => {
    reconnectAttempts.current = 0;
    disconnect();
    setTimeout(() => connect(), 100);
  }, [connect, disconnect]);

  // Reset progress state (call when starting new message)
  const resetProgress = useCallback(() => {
    setProgress(0);
    setStatusMessage('');
    setPhase('idle');
  }, []);

  // Connect when guid is set
  useEffect(() => {
    // Defensive check - handle null, undefined, empty string, and string "null"/"undefined"
    if (!guid || guid === 'null' || guid === 'undefined') {
      console.log('[MCP-WS] No valid GUID, skipping connection');
      return;
    }

    const timer = setTimeout(() => {
      connect();
    }, 200); // Slight delay to ensure Channel 1 connects first

    return () => {
      clearTimeout(timer);
      disconnect();
    };
  }, [guid]);

  return {
    connected,
    progress,
    statusMessage,
    phase,
    reconnect,
    disconnect,
    resetProgress,
  };
}

export default useProgressSocket;
