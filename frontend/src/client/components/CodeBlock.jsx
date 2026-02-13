import { useState } from 'react';
import { Copy, Check } from 'lucide-react';

export function CodeBlock({ children, className = '' }) {
  const [copied, setCopied] = useState(false);

  // Extract language from className (e.g., "language-javascript")
  const match = /language-(\w+)/.exec(className);
  const language = match ? match[1] : '';

  const handleCopy = async () => {
    const code = typeof children === 'string' ? children : children?.props?.children || '';
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group my-3">
      {/* Language badge */}
      {language && (
        <div className="absolute top-0 left-4 px-2 py-0.5 text-xs rounded-b
          dark:bg-gray-700 dark:text-gray-400 bg-gray-200 text-gray-600">
          {language}
        </div>
      )}

      {/* Copy button */}
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity
          dark:bg-gray-700 dark:hover:bg-gray-600 bg-gray-200 hover:bg-gray-300"
        title="Copy code"
      >
        {copied ? (
          <Check className="w-4 h-4 text-green-500" />
        ) : (
          <Copy className="w-4 h-4 dark:text-gray-400 text-gray-600" />
        )}
      </button>

      {/* Code block */}
      <pre className={`p-4 pt-8 rounded-lg overflow-x-auto text-sm
        dark:bg-[#0d0d12] dark:text-gray-300
        bg-gray-100 text-gray-800
        ${className}`}
      >
        <code>{children}</code>
      </pre>
    </div>
  );
}
