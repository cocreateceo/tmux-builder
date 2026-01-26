import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

// Note: StrictMode disabled because xterm.js doesn't handle double mounting well
// StrictMode causes terminal to initialize, cleanup, re-initialize which breaks xterm.js
ReactDOM.createRoot(document.getElementById('root')).render(
  <App />
)
