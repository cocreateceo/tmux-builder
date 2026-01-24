import { useState } from 'react'
import ChatInterface from './components/ChatInterface'

function App() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto p-4 h-screen flex flex-col">
        <header className="mb-4">
          <h1 className="text-3xl font-bold text-gray-800">Tmux Builder</h1>
          <p className="text-gray-600 text-sm">Chat with Claude via tmux sessions</p>
        </header>

        <div className="flex-1 overflow-hidden">
          <ChatInterface />
        </div>
      </div>
    </div>
  )
}

export default App
