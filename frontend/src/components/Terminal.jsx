import { useEffect, useRef, useState } from 'react'
import { Terminal as XTerm } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import { WebLinksAddon } from 'xterm-addon-web-links'
import 'xterm/css/xterm.css'

/**
 * Terminal component using xterm.js with WebSocket streaming.
 *
 * Connects to backend PTY via WebSocket for real-time terminal output.
 */
function Terminal({ guid, onDisconnect }) {
  const terminalRef = useRef(null)
  const xtermRef = useRef(null)
  const wsRef = useRef(null)
  const fitAddonRef = useRef(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!guid || !terminalRef.current) return

    // Initialize xterm.js
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
    })

    // Add addons
    const fitAddon = new FitAddon()
    const webLinksAddon = new WebLinksAddon()
    term.loadAddon(fitAddon)
    term.loadAddon(webLinksAddon)

    // Open terminal in container
    term.open(terminalRef.current)
    fitAddon.fit()

    xtermRef.current = term
    fitAddonRef.current = fitAddon

    // Connect to WebSocket
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//localhost:8000/ws/${guid}`

    term.writeln('\x1b[33m[Connecting to session...]\x1b[0m')

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('WebSocket connected')
      setConnected(true)
      setError(null)
      term.writeln('\x1b[32m[Connected]\x1b[0m')
      term.writeln('')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        switch (data.type) {
          case 'output':
            term.write(data.data)
            break
          case 'ready':
            console.log('Session ready:', data)
            if (data.new_session) {
              term.writeln('\x1b[32m[New session created]\x1b[0m')
            } else {
              term.writeln('\x1b[33m[Reconnected to existing session]\x1b[0m')
            }
            break
          case 'pong':
            // Keepalive response
            break
          case 'error':
            term.writeln(`\x1b[31m[Error: ${data.message}]\x1b[0m`)
            setError(data.message)
            break
          default:
            console.log('Unknown message type:', data.type)
        }
      } catch (e) {
        // Raw text message
        term.write(event.data)
      }
    }

    ws.onclose = (event) => {
      console.log('WebSocket closed:', event.code, event.reason)
      setConnected(false)
      term.writeln('')
      term.writeln('\x1b[31m[Disconnected]\x1b[0m')
      if (onDisconnect) onDisconnect()
    }

    ws.onerror = (event) => {
      console.error('WebSocket error:', event)
      setError('Connection error')
      term.writeln('\x1b[31m[Connection error]\x1b[0m')
    }

    // Handle terminal input
    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'input', data }))
      }
    })

    // Handle resize
    const handleResize = () => {
      if (fitAddonRef.current && xtermRef.current) {
        fitAddonRef.current.fit()
        const { rows, cols } = xtermRef.current
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: 'resize', rows, cols }))
        }
      }
    }

    window.addEventListener('resize', handleResize)

    // Initial resize
    setTimeout(handleResize, 100)

    // Keepalive ping every 30 seconds
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000)

    // Cleanup
    return () => {
      clearInterval(pingInterval)
      window.removeEventListener('resize', handleResize)
      ws.close()
      term.dispose()
    }
  }, [guid, onDisconnect])

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

      {/* Terminal container */}
      <div
        ref={terminalRef}
        className="flex-1 bg-[#1e1e1e]"
        style={{ padding: '8px' }}
      />
    </div>
  )
}

export default Terminal
