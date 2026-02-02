import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CodeBlock } from './CodeBlock';
import { User, Bot, ExternalLink } from 'lucide-react';

function formatTime(timestamp) {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function MessageBubble({ message }) {
  const isUser = message.role === 'user';
  const isDeployment = message.content?.toLowerCase().includes('deployed:') ||
                       message.type === 'deployed';

  // Extract deployed URL if present
  const deployUrlMatch = message.content?.match(/https?:\/\/[^\s]+/);
  const deployUrl = isDeployment ? deployUrlMatch?.[0] : null;

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div
        className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center"
        style={{ background: isUser ? 'var(--primary)' : 'var(--bg-secondary)' }}
      >
        {isUser ? (
          <User className="w-4 h-4 text-white" />
        ) : (
          <Bot className="w-4 h-4" style={{ color: 'var(--text-secondary)' }} />
        )}
      </div>

      {/* Message content */}
      <div className={`flex-1 max-w-[80%] ${isUser ? 'text-right' : ''}`}>
        {/* Header */}
        <div
          className={`flex items-center gap-2 mb-1 text-xs ${isUser ? 'justify-end' : ''}`}
          style={{ color: 'var(--text-muted)' }}
        >
          <span className="font-medium">
            {isUser ? 'You' : 'Claude'}
          </span>
          <span>{formatTime(message.timestamp)}</span>
        </div>

        {/* Content bubble */}
        <div
          className={`rounded-2xl px-4 py-3 inline-block text-left ${isUser ? 'rounded-tr-sm' : 'rounded-tl-sm'}`}
          style={{
            background: isUser
              ? 'transparent'
              : isDeployment
                ? 'rgba(34, 197, 94, 0.15)'
                : 'var(--bg-secondary)',
            color: 'var(--text-primary)',
            border: isUser
              ? '1px solid var(--primary)'
              : isDeployment
                ? '1px solid rgba(34, 197, 94, 0.3)'
                : 'none'
          }}
        >
          {isDeployment && deployUrl ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-green-500 dark:text-green-400">
                <ExternalLink className="w-4 h-4" />
                <span className="font-medium">Deployed Successfully!</span>
              </div>

              {/* Preview placeholder */}
              <div
                className="w-full h-32 rounded-lg flex items-center justify-center border"
                style={{ background: 'var(--bg-primary)', borderColor: 'var(--border-color)' }}
              >
                <span className="text-sm" style={{ color: 'var(--text-muted)' }}>Preview</span>
              </div>

              {/* Link */}
              <a
                href={deployUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                {deployUrl}
              </a>
            </div>
          ) : (
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ node, inline, className, children, ...props }) {
                    if (inline) {
                      return (
                        <code
                          className="px-1.5 py-0.5 rounded text-sm
                            dark:bg-gray-700 dark:text-gray-200
                            bg-gray-200 text-gray-800"
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    }
                    return (
                      <CodeBlock className={className}>
                        {children}
                      </CodeBlock>
                    );
                  },
                  a({ href, children }) {
                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-indigo-400 hover:text-indigo-300 underline"
                      >
                        {children}
                      </a>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
