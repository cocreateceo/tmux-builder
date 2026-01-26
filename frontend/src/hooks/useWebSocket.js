import { useState, useEffect, useRef, useCallback } from 'react';

const WS_BASE_URL = 'ws://localhost:8000';

/**
 * Custom hook for WebSocket communication with auto-reconnect.
 *
 * @param {string} guid - Session GUID
 * @param {object} handlers - Event handlers { onMessage, onStatus, onError, onConnect, onDisconnect }
 * @returns {object} - { connected, status, sendMessage, createSession, reconnect }
 */
export function useWebSocket(guid, handlers = {}) {
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState(null);
  const [history, setHistory] = useState([]);

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const isConnectingRef = useRef(false);
  const handlersRef = useRef(handlers);
  const guidRef = useRef(guid);

  const maxReconnectAttempts = 10;
  const PING_INTERVAL = 30000; // Send ping every 30 seconds

  // Keep refs updated
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    guidRef.current = guid;
  }, [guid]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    const currentGuid = guidRef.current;

    if (!currentGuid) {
      console.log('[WS] No GUID provided');
      return;
    }

    // Prevent multiple simultaneous connection attempts
    if (isConnectingRef.current) {
      console.log('[WS] Already connecting, skipping');
      return;
    }

    // If already connected to the same GUID, skip
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      console.log('[WS] Already connected');
      return;
    }

    // If there's a connection in progress (CONNECTING state), wait for it
    if (wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING) {
      console.log('[WS] Connection in progress, skipping');
      return;
    }

    isConnectingRef.current = true;

    // Clean up any existing connection that's not open
    if (wsRef.current) {
      try {
        wsRef.current.close(1000, 'Reconnecting');
      } catch (e) {
        // Ignore close errors
      }
      wsRef.current = null;
    }

    const wsUrl = `${WS_BASE_URL}/ws/${currentGuid}`;
    console.log(`[WS] Connecting to ${wsUrl}...`);

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[WS] Connected');
      isConnectingRef.current = false;
      setConnected(true);
      reconnectAttempts.current = 0;
      handlersRef.current.onConnect?.();

      // Start keepalive ping interval
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
      pingIntervalRef.current = setInterval(() => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: 'ping' }));
        }
      }, PING_INTERVAL);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('[WS] Received:', data.type);

        switch (data.type) {
          case 'connected':
            setStatus(data.status);
            if (data.history) {
              setHistory(data.history);
              handlersRef.current.onHistory?.(data.history);
            }
            break;

          case 'status':
            setStatus(data);
            handlersRef.current.onStatus?.(data);
            break;

          case 'response':
            handlersRef.current.onMessage?.(data);
            break;

          case 'session_created':
            handlersRef.current.onSessionCreated?.(data);
            break;

          case 'history':
            setHistory(data.messages || []);
            handlersRef.current.onHistory?.(data.messages || []);
            break;

          case 'error':
            console.error('[WS] Error:', data.message);
            handlersRef.current.onError?.(data.message);
            break;

          case 'pong':
            // Keepalive response, ignore
            break;

          default:
            console.log('[WS] Unknown message type:', data.type);
        }
      } catch (err) {
        console.error('[WS] Failed to parse message:', err);
      }
    };

    ws.onclose = (event) => {
      console.log('[WS] Disconnected:', event.code, event.reason);
      isConnectingRef.current = false;
      setConnected(false);

      // Clear ping interval
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = null;
      }

      // Only notify disconnect if this is the current websocket
      if (wsRef.current === ws) {
        handlersRef.current.onDisconnect?.();
        wsRef.current = null;

        // Auto-reconnect if not intentional close (code 1000)
        if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
          console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current + 1}/${maxReconnectAttempts})`);

          // Clear any existing reconnect timeout
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
      console.error('[WS] Error:', error);
      isConnectingRef.current = false;
    };
  }, []); // No dependencies - uses refs

  // Disconnect
  const disconnect = useCallback(() => {
    console.log('[WS] Disconnecting...');

    // Clear ping interval
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }

    // Clear reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Close connection
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

  // Send a chat message
  const sendMessage = useCallback((content) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('[WS] Not connected');
      return false;
    }

    wsRef.current.send(JSON.stringify({
      type: 'send_message',
      content: content
    }));
    return true;
  }, []);

  // Create session via WebSocket
  const createSession = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('[WS] Not connected');
      return false;
    }

    wsRef.current.send(JSON.stringify({
      type: 'create_session'
    }));
    return true;
  }, []);

  // Request status
  const requestStatus = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return false;
    }

    wsRef.current.send(JSON.stringify({
      type: 'get_status'
    }));
    return true;
  }, []);

  // Request history
  const requestHistory = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return false;
    }

    wsRef.current.send(JSON.stringify({
      type: 'get_history'
    }));
    return true;
  }, []);

  // Manual reconnect
  const reconnect = useCallback(() => {
    reconnectAttempts.current = 0;
    disconnect();
    // Small delay before reconnecting
    setTimeout(() => connect(), 100);
  }, [connect, disconnect]);

  // Connect when guid is set, disconnect on unmount or guid change
  useEffect(() => {
    // Don't connect if no guid
    if (!guid) {
      console.log('[WS] No GUID, skipping connection');
      return;
    }

    // Small delay to ensure component is fully mounted
    const timer = setTimeout(() => {
      connect();
    }, 100);

    return () => {
      clearTimeout(timer);
      disconnect();
    };
  }, [guid]); // Only depend on guid, not connect/disconnect

  return {
    connected,
    status,
    history,
    sendMessage,
    createSession,
    requestStatus,
    requestHistory,
    reconnect,
    disconnect
  };
}

export default useWebSocket;
