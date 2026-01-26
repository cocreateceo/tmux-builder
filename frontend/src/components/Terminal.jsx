import { useEffect, useRef, useState, useCallback } from 'react'
import { Terminal as XTerm } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import { WebLinksAddon } from 'xterm-addon-web-links'
import 'xterm/css/xterm.css'

/**
 * Terminal component using xterm.js with WebSocket streaming.
 */
function Terminal({ guid, onDisconnect }) {
  const containerRef = useRef(null)
  const termRef = useRef(null)
  const fitAddonRef = useRef(null)
  const wsRef = useRef(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)
  const mountedRef = useRef(true)

  // Connect WebSocket
  const connectWebSocket = useCallback(() => {
    if (!guid || !termRef.current) return

    const term = termRef.current

    // Close existing connection if any
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//localhost:8000/ws/${guid}`

    console.log('[Terminal] Connecting to WebSocket:', wsUrl)
    term.writeln('\x1b[33m[Connecting...]\x1b[0m')

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) {
        ws.close()
        return
      }
      console.log('[Terminal] WebSocket connected')
      setConnected(true)
      setError(null)
      term.writeln('\x1b[32m[Connected]\x1b[0m')
    }

    ws.onmessage = (event) => {
      if (!mountedRef.current) return
      try {
        const data = JSON.parse(event.data)
        switch (data.type) {
          case 'output':
            term.write(data.data)
            break
          case 'ready':
            console.log('[Terminal] Session ready:', data)
            if (data.new_session) {
              term.writeln('\x1b[32m[New session created]\x1b[0m')
            } else {
              term.writeln('\x1b[33m[Reconnected to existing session]\x1b[0m')
            }
            break
          case 'pong':
            break
          case 'error':
            term.writeln(`\x1b[31m[Error: ${data.message}]\x1b[0m`)
            setError(data.message)
            break
          default:
            console.log('[Terminal] Unknown message type:', data.type)
        }
      } catch (e) {
        term.write(event.data)
      }
    }

    ws.onclose = (event) => {
      if (!mountedRef.current) return
      console.log('[Terminal] WebSocket closed:', event.code)
      setConnected(false)
      term.writeln('')
      term.writeln('\x1b[31m[Disconnected]\x1b[0m')
    }

    ws.onerror = () => {
      if (!mountedRef.current) return
      setError('Connection error')
      term.writeln('\x1b[31m[Connection error]\x1b[0m')
    }

  }, [guid])

  // Initialize terminal
  useEffect(() => {
    if (!guid || !containerRef.current) return

    mountedRef.current = true

    // Check if already initialized
    if (termRef.current) {
      // Already have a terminal, just reconnect WebSocket if needed
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connectWebSocket()
      }
      return
    }

    // Wait for container dimensions
    const rect = containerRef.current.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) {
      const timer = setTimeout(() => {
        // Re-trigger effect
        if (containerRef.current) {
          containerRef.current.style.minHeight = '401px'
          containerRef.current.style.minHeight = '400px'
        }
      }, 100)
      return () => clearTimeout(timer)
    }

    console.log('[Terminal] Initializing with dimensions:', rect.width, 'x', rect.height)

    // Create terminal
    const term = new XTerm({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#ffffff',
      },
      scrollback: 10000,
      convertEol: true,
    })

    const fitAddon = new FitAddon()
    const webLinksAddon = new WebLinksAddon()
    term.loadAddon(fitAddon)
    term.loadAddon(webLinksAddon)

    term.open(containerRef.current)
    termRef.current = term
    fitAddonRef.current = fitAddon

    // Fit and focus
    setTimeout(() => {
      try {
        fitAddon.fit()
        term.focus()
        console.log('[Terminal] Fit successful, rows:', term.rows, 'cols:', term.cols)
      } catch (e) {
        console.warn('[Terminal] Fit failed:', e.message)
      }
    }, 50)

    // Handle input
    term.onData((data) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'input', data }))
      }
    })

    // Handle resize
    const handleResize = () => {
      try {
        fitAddonRef.current?.fit()
        if (wsRef.current?.readyState === WebSocket.OPEN && termRef.current) {
          const { rows, cols } = termRef.current
          wsRef.current.send(JSON.stringify({ type: 'resize', rows, cols }))
        }
      } catch (e) {
        // Ignore
      }
    }
    window.addEventListener('resize', handleResize)

    // Keepalive
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000)

    // Connect WebSocket
    connectWebSocket()

    // Cleanup
    return () => {
      mountedRef.current = false
      clearInterval(pingInterval)
      window.removeEventListener('resize', handleResize)
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      if (termRef.current) {
        termRef.current.dispose()
        termRef.current = null
      }
    }
  }, [guid, connectWebSocket])

  // Handle click - focus or reconnect
  const handleClick = () => {
    if (termRef.current) {
      termRef.current.focus()
      // If disconnected, try to reconnect
      if (!connected && wsRef.current?.readyState !== WebSocket.OPEN) {
        connectWebSocket()
      }
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Status bar */}
      <div className="flex items-center justify-between px-3 py-2 bg-gray-800 text-sm">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`}></span>
          <span className="text-gray-300">
            {connected ? 'Connected' : 'Disconnected'}
          </span>
          {guid && (
            <span className="text-gray-500 text-xs ml-2">
              Session: {guid.substring(0, 8)}...
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!connected && (
            <button
              onClick={connectWebSocket}
              className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Reconnect
            </button>
          )}
          {error && (
            <span className="text-red-400 text-xs">{error}</span>
          )}
        </div>
      </div>

      {/* Terminal container */}
      <div
        ref={containerRef}
        className="flex-1 bg-[#1e1e1e] cursor-text"
        style={{
          padding: '8px',
          minHeight: '400px',
          height: '100%',
          width: '100%',
          overflow: 'hidden'
        }}
        onClick={handleClick}
      />
    </div>
  )
}

export default Terminal
