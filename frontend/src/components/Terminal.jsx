import { useEffect, useRef, useState, useCallback } from 'react'
import { Terminal as XTerm } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import { WebLinksAddon } from 'xterm-addon-web-links'
import 'xterm/css/xterm.css'

/**
 * Terminal component using xterm.js with WebSocket streaming.
 *
 * Uses defensive initialization to avoid xterm.js lifecycle issues.
 */
function Terminal({ guid, onDisconnect }) {
  const containerRef = useRef(null)
  const terminalInstanceRef = useRef(null)
  const wsInstanceRef = useRef(null)
  const cleanupCalledRef = useRef(false)
  const initializingRef = useRef(false)

  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)
  const [ready, setReady] = useState(false)

  // Safe cleanup function
  const cleanup = useCallback(() => {
    if (cleanupCalledRef.current) return
    cleanupCalledRef.current = true

    console.log('[Terminal] Cleanup called')

    // Close WebSocket first
    if (wsInstanceRef.current) {
      try {
        wsInstanceRef.current.close()
      } catch (e) {
        console.warn('[Terminal] WebSocket close error:', e)
      }
      wsInstanceRef.current = null
    }

    // Dispose terminal
    if (terminalInstanceRef.current) {
      try {
        terminalInstanceRef.current.term.dispose()
      } catch (e) {
        console.warn('[Terminal] Terminal dispose error:', e)
      }
      terminalInstanceRef.current = null
    }
  }, [])

  // Initialize terminal when container is ready
  useEffect(() => {
    if (!guid) return

    // Reset cleanup flag for new initialization
    cleanupCalledRef.current = false

    // Wait for container to be in DOM and have dimensions
    const initTerminal = () => {
      const container = containerRef.current
      if (!container) {
        console.log('[Terminal] Container not ready, retrying...')
        requestAnimationFrame(initTerminal)
        return
      }

      // Check container has actual dimensions
      const rect = container.getBoundingClientRect()
      if (rect.width === 0 || rect.height === 0) {
        console.log('[Terminal] Container has no dimensions, retrying...')
        requestAnimationFrame(initTerminal)
        return
      }

      // Prevent double initialization
      if (initializingRef.current || terminalInstanceRef.current) {
        console.log('[Terminal] Already initializing or initialized')
        return
      }
      initializingRef.current = true

      console.log('[Terminal] Initializing with dimensions:', rect.width, 'x', rect.height)

      try {
        // Create terminal
        const term = new XTerm({
          cursorBlink: true,
          fontSize: 14,
          fontFamily: 'Menlo, Monaco, "Courier New", monospace',
          theme: {
            background: '#1e1e1e',
            foreground: '#d4d4d4',
            cursor: '#ffffff',
            cursorAccent: '#000000',
            selection: 'rgba(255, 255, 255, 0.3)',
            black: '#000000',
            red: '#cd3131',
            green: '#0dbc79',
            yellow: '#e5e510',
            blue: '#2472c8',
            magenta: '#bc3fbc',
            cyan: '#11a8cd',
            white: '#e5e5e5',
            brightBlack: '#666666',
            brightRed: '#f14c4c',
            brightGreen: '#23d18b',
            brightYellow: '#f5f543',
            brightBlue: '#3b8eea',
            brightMagenta: '#d670d6',
            brightCyan: '#29b8db',
            brightWhite: '#ffffff',
          },
          scrollback: 10000,
          convertEol: true,
          allowProposedApi: true,
        })

        // Create addons
        const fitAddon = new FitAddon()
        const webLinksAddon = new WebLinksAddon()

        term.loadAddon(fitAddon)
        term.loadAddon(webLinksAddon)

        // Open in container
        term.open(container)

        // Store instance
        terminalInstanceRef.current = { term, fitAddon }

        // Fit after a short delay to ensure DOM is fully ready
        setTimeout(() => {
          if (terminalInstanceRef.current && !cleanupCalledRef.current) {
            try {
              fitAddon.fit()
              setReady(true)
              console.log('[Terminal] Fit successful, rows:', term.rows, 'cols:', term.cols)
            } catch (e) {
              console.warn('[Terminal] Fit failed:', e.message)
              setReady(true) // Continue anyway
            }
          }
        }, 50)

        term.writeln('\x1b[33m[Connecting to session...]\x1b[0m')

        // Connect WebSocket
        connectWebSocket(term)

        // Handle terminal input
        term.onData((data) => {
          if (wsInstanceRef.current?.readyState === WebSocket.OPEN) {
            wsInstanceRef.current.send(JSON.stringify({ type: 'input', data }))
          }
        })

        // Handle resize
        const handleResize = () => {
          if (!terminalInstanceRef.current || cleanupCalledRef.current) return
          try {
            terminalInstanceRef.current.fitAddon.fit()
            if (wsInstanceRef.current?.readyState === WebSocket.OPEN) {
              const { rows, cols } = terminalInstanceRef.current.term
              wsInstanceRef.current.send(JSON.stringify({ type: 'resize', rows, cols }))
            }
          } catch (e) {
            // Ignore resize errors
          }
        }

        window.addEventListener('resize', handleResize)

        // Store resize handler for cleanup
        terminalInstanceRef.current.handleResize = handleResize

      } catch (e) {
        console.error('[Terminal] Initialization error:', e)
        setError('Failed to initialize terminal')
      } finally {
        initializingRef.current = false
      }
    }

    const connectWebSocket = (term) => {
      if (cleanupCalledRef.current) return

      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${wsProtocol}//localhost:8000/ws/${guid}`

      console.log('[Terminal] Connecting to WebSocket:', wsUrl)
      const ws = new WebSocket(wsUrl)
      wsInstanceRef.current = ws

      ws.onopen = () => {
        if (cleanupCalledRef.current) {
          ws.close()
          return
        }
        console.log('[Terminal] WebSocket connected')
        setConnected(true)
        setError(null)
        term.writeln('\x1b[32m[Connected]\x1b[0m')
        term.writeln('')
      }

      ws.onmessage = (event) => {
        if (cleanupCalledRef.current) return
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
          // Not JSON, write as raw output
          term.write(event.data)
        }
      }

      ws.onclose = (event) => {
        if (cleanupCalledRef.current) return
        console.log('[Terminal] WebSocket closed:', event.code)
        setConnected(false)
        term.writeln('')
        term.writeln('\x1b[31m[Disconnected]\x1b[0m')
        if (onDisconnect) onDisconnect()
      }

      ws.onerror = (event) => {
        if (cleanupCalledRef.current) return
        console.error('[Terminal] WebSocket error:', event)
        setError('Connection error')
        term.writeln('\x1b[31m[Connection error]\x1b[0m')
      }

      // Keepalive ping
      const pingInterval = setInterval(() => {
        if (wsInstanceRef.current?.readyState === WebSocket.OPEN && !cleanupCalledRef.current) {
          wsInstanceRef.current.send(JSON.stringify({ type: 'ping' }))
        } else if (cleanupCalledRef.current) {
          clearInterval(pingInterval)
        }
      }, 30000)

      // Store interval for cleanup
      if (terminalInstanceRef.current) {
        terminalInstanceRef.current.pingInterval = pingInterval
      }
    }

    // Start initialization after a brief delay to ensure React render is complete
    const initTimeout = setTimeout(initTerminal, 100)

    // Cleanup on unmount
    return () => {
      clearTimeout(initTimeout)

      if (terminalInstanceRef.current) {
        if (terminalInstanceRef.current.pingInterval) {
          clearInterval(terminalInstanceRef.current.pingInterval)
        }
        if (terminalInstanceRef.current.handleResize) {
          window.removeEventListener('resize', terminalInstanceRef.current.handleResize)
        }
      }

      cleanup()
      initializingRef.current = false
    }
  }, [guid, onDisconnect, cleanup])

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
        {error && (
          <span className="text-red-400 text-xs">{error}</span>
        )}
      </div>

      {/* Terminal container - must have explicit dimensions */}
      <div
        ref={containerRef}
        className="flex-1 bg-[#1e1e1e]"
        style={{
          padding: '8px',
          minHeight: '400px',
          height: '100%',
          width: '100%',
          overflow: 'hidden'
        }}
      />
    </div>
  )
}

export default Terminal
