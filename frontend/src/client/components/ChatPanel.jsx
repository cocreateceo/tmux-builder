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
    <div
      className="flex-1 flex flex-col min-w-0"
      style={{ background: 'var(--bg-primary)' }}
    >
      {/* Header */}
      {project && (
        <div
          className="h-14 px-4 flex items-center justify-between border-b"
          style={{ borderColor: 'var(--border-color)' }}
        >
          <div className="min-w-0">
            <h2 className="font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
              {project.name}
            </h2>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Started {new Date(project.created_at).toLocaleDateString()} • {project.message_count || 0} messages
            </p>
          </div>
          <button
            onClick={onProjectAction}
            className="p-2 rounded-lg hover:opacity-80"
            style={{ color: 'var(--text-muted)' }}
          >
            <MoreHorizontal className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex-1 flex items-center justify-center h-full">
            <div className="text-center" style={{ color: 'var(--text-muted)' }}>
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
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center"
              style={{ background: 'var(--bg-secondary)' }}
            >
              <Loader className="w-4 h-4 animate-spin" style={{ color: 'var(--text-muted)' }} />
            </div>
            <div
              className="rounded-2xl rounded-tl-sm px-4 py-3"
              style={{ background: 'var(--bg-secondary)' }}
            >
              <div className="flex gap-1">
                <span className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--text-muted)', animationDelay: '0ms' }} />
                <span className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--text-muted)', animationDelay: '150ms' }} />
                <span className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--text-muted)', animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="p-4 border-t" style={{ borderColor: 'var(--border-color)' }}>
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          {/* Attachment button */}
          <button
            type="button"
            className="p-2 rounded-lg hover:opacity-80"
            style={{ color: 'var(--text-muted)' }}
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
              className="w-full px-4 py-3 text-sm rounded-xl border resize-none focus:outline-none disabled:opacity-50"
              style={{
                background: 'var(--bg-secondary)',
                borderColor: 'var(--border-color)',
                color: 'var(--text-primary)'
              }}
            />
          </div>

          {/* Voice button */}
          <button
            type="button"
            onClick={handleVoiceInput}
            className="p-2 rounded-lg transition-colors hover:opacity-80"
            style={{
              background: isRecording ? '#ef4444' : 'transparent',
              color: isRecording ? 'white' : 'var(--text-muted)'
            }}
            title="Voice input"
          >
            <Mic className="w-5 h-5" />
          </button>

          {/* Send button */}
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="p-3 rounded-xl text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors hover:opacity-90"
            style={{ background: 'var(--primary)' }}
          >
            <Send className="w-5 h-5" />
          </button>
        </form>
      </div>
    </div>
  );
}
