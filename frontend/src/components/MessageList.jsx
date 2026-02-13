import { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function MessageList({ messages, loading }) {
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  return (
    <div className="space-y-4">
      {messages.length === 0 && !loading && (
        <div className="text-center text-gray-500 py-8">
          <p>No messages yet. Start a conversation!</p>
        </div>
      )}

      {messages.map((message, index) => (
        <div
          key={index}
          className={`flex ${
            message.role === 'user' ? 'justify-end' : 'justify-start'
          }`}
        >
          <div
            className={`max-w-[80%] rounded-lg p-4 ${
              message.role === 'user'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-800'
            }`}
          >
            {/* Role indicator */}
            <div className="text-xs font-semibold mb-2 opacity-75">
              {message.role === 'user' ? 'You' : 'Claude'}
            </div>

            {/* Message content */}
            <div className="prose prose-sm max-w-none prose-headings:text-gray-800 prose-headings:font-bold prose-h2:text-base prose-h3:text-sm prose-ul:my-2 prose-li:my-0.5 prose-p:my-2 prose-strong:text-gray-900">
              {message.role === 'assistant' ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h2: ({ children }) => <h2 className="text-base font-bold mt-3 mb-2 text-gray-800">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-sm font-semibold mt-2 mb-1 text-gray-700">{children}</h3>,
                    ul: ({ children }) => <ul className="list-disc pl-4 my-2 space-y-1">{children}</ul>,
                    li: ({ children }) => <li className="text-sm">{children}</li>,
                    p: ({ children }) => <p className="my-2 text-sm">{children}</p>,
                    strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
                    a: ({ href, children }) => <a href={href} className="text-blue-600 underline" target="_blank" rel="noopener noreferrer">{children}</a>,
                    code: ({ node, inline, className, children, ...props }) => {
                      return !inline ? (
                        <pre className="bg-gray-800 text-gray-100 p-3 rounded overflow-x-auto text-xs">
                          <code className={className} {...props}>
                            {children}
                          </code>
                        </pre>
                      ) : (
                        <code className="bg-gray-200 text-gray-800 px-1 py-0.5 rounded text-xs" {...props}>
                          {children}
                        </code>
                      );
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              ) : (
                <p className="whitespace-pre-wrap">{message.content}</p>
              )}
            </div>

            {/* Timestamp */}
            <div className="text-xs mt-2 opacity-50">
              {new Date(message.timestamp).toLocaleTimeString()}
            </div>
          </div>
        </div>
      ))}

      {loading && (
        <div className="flex justify-start">
          <div className="bg-gray-100 rounded-lg p-4">
            <div className="flex space-x-2">
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
            </div>
          </div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
}

export default MessageList;
