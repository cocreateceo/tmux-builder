import { useState, useRef, useEffect } from 'react';
import { Send, Paperclip, Mic, Loader, MoreHorizontal, FileText, Upload } from 'lucide-react';
import { MessageBubble } from './MessageBubble';

export function ChatPanel({
  project,
  messages,
  loading,
  onSendMessage,
  onFileUpload,
  onProjectAction
}) {
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

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

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = [
      'text/plain',
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'image/jpeg',
      'image/png'
    ];
    const allowedExtensions = ['.txt', '.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();

    if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(ext)) {
      alert('Please upload a .txt, .pdf, .doc, .docx, .jpg, or .png file');
      return;
    }

    // Max 10MB
    if (file.size > 10 * 1024 * 1024) {
      alert('File size must be less than 10MB');
      return;
    }

    setSelectedFile(file);
  };

  const handleFileUpload = async () => {
    if (!selectedFile || uploadingFile || !onFileUpload) return;

    setUploadingFile(true);
    try {
      await onFileUpload(selectedFile);
      setSelectedFile(null);
      // Clear file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error) {
      console.error('File upload failed:', error);
      alert('Failed to upload file. Please try again.');
    } finally {
      setUploadingFile(false);
    }
  };

  const clearSelectedFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
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

      {/* Selected file preview */}
      {selectedFile && (
        <div className="px-4 py-2 border-t" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}>
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4" style={{ color: 'var(--primary)' }} />
            <span className="text-sm flex-1 truncate" style={{ color: 'var(--text-primary)' }}>
              {selectedFile.name}
            </span>
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {(selectedFile.size / 1024).toFixed(1)} KB
            </span>
            <button
              onClick={clearSelectedFile}
              className="text-xs px-2 py-1 rounded hover:opacity-80"
              style={{ color: 'var(--text-muted)' }}
            >
              ✕
            </button>
            <button
              onClick={handleFileUpload}
              disabled={uploadingFile}
              className="text-xs px-3 py-1 rounded-lg text-white disabled:opacity-50"
              style={{ background: 'var(--primary)' }}
            >
              {uploadingFile ? 'Uploading...' : 'Upload & Build'}
            </button>
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="p-4 border-t" style={{ borderColor: 'var(--border-color)' }}>
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.pdf,.doc,.docx,.jpg,.jpeg,.png"
            onChange={handleFileSelect}
            className="hidden"
          />

          {/* Text input */}
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message..."
              rows={1}
              disabled={loading || uploadingFile}
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

          {/* Attachment button (moved to right) */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="p-2 rounded-lg hover:opacity-80"
            style={{ color: 'var(--text-muted)' }}
            title="Upload document (.txt, .pdf, .doc, .docx, .jpg, .png)"
          >
            <Paperclip className="w-5 h-5" />
          </button>

          {/* Send button */}
          <button
            type="submit"
            disabled={!input.trim() || loading || uploadingFile}
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
