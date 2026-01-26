import { useState } from 'react'
import ChatInterface from './components/ChatInterface'
import Terminal from './components/Terminal'

function App() {
  const [mode, setMode] = useState('terminal') // 'chat' or 'terminal'
  const [guid, setGuid] = useState(null)
  const [sessionInput, setSessionInput] = useState('')

  const handleConnect = () => {
    if (sessionInput.trim()) {
      setGuid(sessionInput.trim())
    } else {
      // Generate a simple guid for demo
      const newGuid = crypto.randomUUID().replace(/-/g, '')
      setGuid(newGuid)
    }
  }

  const handleDisconnect = () => {
    setGuid(null)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-gray-800">
      <div className="container mx-auto p-4 h-screen flex flex-col">
        {/* Header */}
        <header className="mb-4 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">Tmux Builder</h1>
            <p className="text-gray-400 text-sm">
              {mode === 'terminal'
                ? 'Real-time terminal streaming via WebSocket'
                : 'Chat with Claude via PTY sessions'}
            </p>
          </div>

          {/* Mode toggle */}
          <div className="flex items-center gap-4">
            <div className="flex bg-gray-700 rounded-lg p-1">
              <button
                onClick={() => setMode('terminal')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  mode === 'terminal'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:text-white'
                }`}
              >
                Terminal
              </button>
              <button
                onClick={() => setMode('chat')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  mode === 'chat'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:text-white'
                }`}
              >
                Chat
              </button>
            </div>
          </div>
        </header>

        {/* Main content - use CSS to hide/show instead of unmount */}
        <div className="flex-1 overflow-hidden rounded-lg border border-gray-700 relative">
          {/* Terminal mode */}
          <div
            className={`absolute inset-0 ${mode === 'terminal' ? 'visible' : 'invisible'}`}
            style={{ zIndex: mode === 'terminal' ? 10 : 0 }}
          >
            {guid ? (
              <Terminal guid={guid} onDisconnect={handleDisconnect} />
            ) : (
              <div className="h-full flex items-center justify-center bg-gray-800">
                <div className="text-center p-8">
                  <h2 className="text-xl font-semibold text-white mb-4">
                    Connect to Terminal Session
                  </h2>
                  <p className="text-gray-400 mb-6">
                    Enter an existing session GUID or create a new one
                  </p>
                  <div className="flex gap-2 max-w-md mx-auto">
                    <input
                      type="text"
                      placeholder="Session GUID (optional)"
                      value={sessionInput}
                      onChange={(e) => setSessionInput(e.target.value)}
                      className="flex-1 px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
                    />
                    <button
                      onClick={handleConnect}
                      className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                    >
                      {sessionInput.trim() ? 'Connect' : 'New Session'}
                    </button>
                  </div>
                  <p className="text-gray-500 text-sm mt-4">
                    Leave empty to create a new Claude CLI session
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Chat mode */}
          <div
            className={`absolute inset-0 ${mode === 'chat' ? 'visible' : 'invisible'}`}
            style={{ zIndex: mode === 'chat' ? 10 : 0 }}
          >
            <ChatInterface />
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
