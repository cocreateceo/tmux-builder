import { useState } from 'react';
import {
  MessageSquare,
  ExternalLink,
  MoreHorizontal,
  Pencil,
  Copy,
  Share2,
  Download,
  Archive,
  Trash2,
  CheckCircle,
  Circle,
  Loader
} from 'lucide-react';

function getStatusColor(status) {
  switch (status) {
    case 'deployed':
      return 'bg-green-500';
    case 'completed':
      return 'bg-blue-500';
    case 'active':
      return 'bg-yellow-500';
    default:
      return 'bg-gray-400';
  }
}

function formatTimeAgo(dateString) {
  if (!dateString) return '';
  const date = new Date(dateString);
  const now = new Date();
  const seconds = Math.floor((now - date) / 1000);

  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return date.toLocaleDateString();
}

export function ProjectCard({
  project,
  isActive,
  onClick,
  onRename,
  onDuplicate,
  onArchive,
  onDelete,
  onShare,
  onDownload
}) {
  const [showMenu, setShowMenu] = useState(false);

  const handleMenuAction = (action, e) => {
    e.stopPropagation();
    setShowMenu(false);
    action();
  };

  return (
    <div
      onClick={onClick}
      className={`p-3 rounded-lg cursor-pointer transition-all border
        ${isActive
          ? 'dark:bg-indigo-500/20 dark:border-indigo-500/50 bg-indigo-50 border-indigo-200'
          : 'dark:bg-[#1a1a24] dark:border-gray-800 dark:hover:bg-[#1e1e2a] bg-white border-gray-200 hover:bg-gray-50'
        }`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${getStatusColor(project.status)}`} />
          <h3 className="font-medium text-sm truncate dark:text-white text-gray-900">
            {project.name}
          </h3>
        </div>

        {/* Menu button */}
        <div className="relative">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowMenu(!showMenu);
            }}
            className="p-1 rounded hover:bg-black/10 dark:hover:bg-white/10"
          >
            <MoreHorizontal className="w-4 h-4 dark:text-gray-400 text-gray-500" />
          </button>

          {showMenu && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowMenu(false);
                }}
              />
              <div className="absolute right-0 top-full mt-1 z-20 w-40 py-1 rounded-lg shadow-lg border
                dark:bg-[#1a1a24] dark:border-gray-700 bg-white border-gray-200">
                <button
                  onClick={(e) => handleMenuAction(onRename, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2
                    dark:hover:bg-gray-800 hover:bg-gray-100 dark:text-gray-300 text-gray-700"
                >
                  <Pencil className="w-3.5 h-3.5" /> Rename
                </button>
                <button
                  onClick={(e) => handleMenuAction(onDuplicate, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2
                    dark:hover:bg-gray-800 hover:bg-gray-100 dark:text-gray-300 text-gray-700"
                >
                  <Copy className="w-3.5 h-3.5" /> Duplicate
                </button>
                <button
                  onClick={(e) => handleMenuAction(onShare, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2
                    dark:hover:bg-gray-800 hover:bg-gray-100 dark:text-gray-300 text-gray-700"
                >
                  <Share2 className="w-3.5 h-3.5" /> Share
                </button>
                <button
                  onClick={(e) => handleMenuAction(onDownload, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2
                    dark:hover:bg-gray-800 hover:bg-gray-100 dark:text-gray-300 text-gray-700"
                >
                  <Download className="w-3.5 h-3.5" /> Download
                </button>
                <hr className="my-1 dark:border-gray-700 border-gray-200" />
                <button
                  onClick={(e) => handleMenuAction(onArchive, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2
                    dark:hover:bg-gray-800 hover:bg-gray-100 dark:text-gray-300 text-gray-700"
                >
                  <Archive className="w-3.5 h-3.5" /> Archive
                </button>
                <button
                  onClick={(e) => handleMenuAction(onDelete, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2 text-red-500
                    dark:hover:bg-gray-800 hover:bg-gray-100"
                >
                  <Trash2 className="w-3.5 h-3.5" /> Delete
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Description snippet */}
      <p className="text-xs dark:text-gray-400 text-gray-500 truncate mb-2">
        {project.initial_request || 'No description'}
      </p>

      {/* Footer row */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-3 dark:text-gray-500 text-gray-400">
          <span className="flex items-center gap-1">
            <MessageSquare className="w-3 h-3" />
            {project.message_count || 0}
          </span>
          <span>{formatTimeAgo(project.updated_at || project.created_at)}</span>
        </div>

        {project.deployed_url && (
          <a
            href={project.deployed_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-green-500 hover:text-green-400 flex items-center gap-1"
          >
            <ExternalLink className="w-3 h-3" />
            <span>Live</span>
          </a>
        )}
      </div>
    </div>
  );
}
