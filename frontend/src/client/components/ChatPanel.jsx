import { useState, useRef, useEffect } from 'react';
import { Send, Paperclip, Mic, Loader, MoreHorizontal } from 'lucide-react';
import { MessageBubble } from './MessageBubble';

export function ChatPanel({
  project,
  messages,
  loading,
  onSendMessage,
  onProjectAction
}) {
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    onSendMessage(input.trim());
    setInput('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleVoiceInput = () => {
    // Placeholder for voice input
    setIsRecording(!isRecording);
    // TODO: Implement Web Speech API
  };

  return (
    <div className="flex-1 flex flex-col min-w-0
      dark:bg-[#0a0a0f] bg-white">

      {/* Header */}
      {project && (
        <div className="h-14 px-4 flex items-center justify-between border-b
          dark:border-gray-800 border-gray-200">
          <div className="min-w-0">
            <h2 className="font-semibold truncate dark:text-white text-gray-900">
              {project.name}
            </h2>
            <p className="text-xs dark:text-gray-500 text-gray-400">
              Started {new Date(project.created_at).toLocaleDateString()} • {project.message_count || 0} messages
            </p>
          </div>
          <button
            onClick={onProjectAction}
            className="p-2 rounded-lg dark:hover:bg-gray-800 hover:bg-gray-100"
          >
            <MoreHorizontal className="w-5 h-5 dark:text-gray-400 text-gray-500" />
          </button>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex-1 flex items-center justify-center h-full">
            <div className="text-center dark:text-gray-500 text-gray-400">
              <p className="text-lg mb-2">No messages yet</p>
              <p className="text-sm">Start a conversation to begin building</p>
            </div>
          </div>
        ) : (
          messages.map((message, index) => (
            <MessageBubble key={index} message={message} />
          ))
        )}

        {/* Typing indicator */}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full dark:bg-gray-700 bg-gray-200
              flex items-center justify-center">
              <Loader className="w-4 h-4 dark:text-gray-400 text-gray-500 animate-spin" />
            </div>
            <div className="dark:bg-[#1a1a24] bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="p-4 border-t dark:border-gray-800 border-gray-200">
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          {/* Attachment button */}
          <button
            type="button"
            className="p-2 rounded-lg dark:hover:bg-gray-800 hover:bg-gray-100
              dark:text-gray-400 text-gray-500"
            title="Attach file"
          >
            <Paperclip className="w-5 h-5" />
          </button>

          {/* Text input */}
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message..."
              rows={1}
              disabled={loading}
              className="w-full px-4 py-3 text-sm rounded-xl border resize-none
                dark:bg-[#1a1a24] dark:border-gray-700 dark:text-white dark:placeholder-gray-500
                bg-gray-50 border-gray-200 text-gray-900 placeholder-gray-400
                focus:outline-none focus:ring-2 focus:ring-indigo-500/50
                disabled:opacity-50"
            />
          </div>

          {/* Voice button */}
          <button
            type="button"
            onClick={handleVoiceInput}
            className={`p-2 rounded-lg transition-colors
              ${isRecording
                ? 'bg-red-500 text-white'
                : 'dark:hover:bg-gray-800 hover:bg-gray-100 dark:text-gray-400 text-gray-500'
              }`}
            title="Voice input"
          >
            <Mic className="w-5 h-5" />
          </button>

          {/* Send button */}
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="p-3 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white
              disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </form>
      </div>
    </div>
  );
}
