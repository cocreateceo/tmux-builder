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
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
        ${isUser
          ? 'bg-indigo-500'
          : 'dark:bg-gray-700 bg-gray-200'
        }`}
      >
        {isUser ? (
          <User className="w-4 h-4 text-white" />
        ) : (
          <Bot className="w-4 h-4 dark:text-gray-300 text-gray-600" />
        )}
      </div>

      {/* Message content */}
      <div className={`flex-1 max-w-[80%] ${isUser ? 'text-right' : ''}`}>
        {/* Header */}
        <div className={`flex items-center gap-2 mb-1 text-xs
          dark:text-gray-500 text-gray-400
          ${isUser ? 'justify-end' : ''}`}
        >
          <span className="font-medium">
            {isUser ? 'You' : 'Claude'}
          </span>
          <span>{formatTime(message.timestamp)}</span>
        </div>

        {/* Content bubble */}
        <div className={`rounded-2xl px-4 py-3 inline-block text-left
          ${isUser
            ? 'bg-indigo-500 text-white rounded-tr-sm'
            : isDeployment
              ? 'dark:bg-green-500/20 dark:border-green-500/30 bg-green-50 border border-green-200 rounded-tl-sm'
              : 'dark:bg-[#1a1a24] dark:text-gray-200 bg-gray-100 text-gray-800 rounded-tl-sm'
          }`}
        >
          {isDeployment && deployUrl ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-green-500 dark:text-green-400">
                <ExternalLink className="w-4 h-4" />
                <span className="font-medium">Deployed Successfully!</span>
              </div>

              {/* Preview placeholder */}
              <div className="w-full h-32 rounded-lg bg-gray-800/50 flex items-center justify-center
                border dark:border-gray-700 border-gray-300">
                <span className="text-sm dark:text-gray-400 text-gray-500">Preview</span>
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
            <div className={`prose prose-sm max-w-none
              ${isUser
                ? 'prose-invert'
                : 'dark:prose-invert'
              }`}
            >
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
