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
      className="p-3 rounded-lg cursor-pointer transition-all border hover:opacity-90"
      style={{
        background: isActive ? 'rgba(252, 42, 13, 0.15)' : 'var(--bg-secondary)',
        borderColor: isActive ? 'var(--primary)' : 'var(--border-color)'
      }}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${getStatusColor(project.status)}`} />
          <h3 className="font-medium text-sm truncate" style={{ color: 'var(--text-primary)' }}>
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
            className="p-1 rounded hover:opacity-80"
          >
            <MoreHorizontal className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
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
              <div
                className="absolute right-0 top-full mt-1 z-20 w-40 py-1 rounded-lg shadow-lg border"
                style={{ background: 'var(--bg-secondary)', borderColor: 'var(--border-color)' }}
              >
                <button
                  onClick={(e) => handleMenuAction(onRename, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2 hover:opacity-80"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  <Pencil className="w-3.5 h-3.5" /> Rename
                </button>
                <button
                  onClick={(e) => handleMenuAction(onDuplicate, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2 hover:opacity-80"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  <Copy className="w-3.5 h-3.5" /> Duplicate
                </button>
                <button
                  onClick={(e) => handleMenuAction(onShare, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2 hover:opacity-80"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  <Share2 className="w-3.5 h-3.5" /> Share
                </button>
                <button
                  onClick={(e) => handleMenuAction(onDownload, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2 hover:opacity-80"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  <Download className="w-3.5 h-3.5" /> Download
                </button>
                <hr className="my-1" style={{ borderColor: 'var(--border-color)' }} />
                <button
                  onClick={(e) => handleMenuAction(onArchive, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2 hover:opacity-80"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  <Archive className="w-3.5 h-3.5" /> Archive
                </button>
                <button
                  onClick={(e) => handleMenuAction(onDelete, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2 text-red-500 hover:opacity-80"
                >
                  <Trash2 className="w-3.5 h-3.5" /> Delete
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Description snippet */}
      <p className="text-xs truncate mb-2" style={{ color: 'var(--text-muted)' }}>
        {project.initial_request || 'No description'}
      </p>

      {/* Footer row */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-3" style={{ color: 'var(--text-muted)' }}>
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
