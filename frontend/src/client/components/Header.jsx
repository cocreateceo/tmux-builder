import { Bell } from 'lucide-react';

export function Header({ client, connected }) {
  return (
    <header
      className="h-14 px-4 flex items-center justify-between border-b"
      style={{
        background: 'var(--bg-card)',
        borderColor: 'var(--border-color)',
        backdropFilter: 'blur(20px)'
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ background: 'var(--primary)' }}
        >
          <span className="text-white font-bold text-sm">TB</span>
        </div>
        <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
          Tmux Builder
        </span>

        {/* Connection status */}
        <div className="flex items-center gap-1.5 ml-4">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3">
        {/* Notifications */}
        <button
          className="p-2 rounded-lg transition-colors relative hover:opacity-80"
          style={{ color: 'var(--text-muted)' }}
        >
          <Bell className="w-5 h-5" />
        </button>

        {/* User */}
        {client && (
          <div
            className="flex items-center gap-2 pl-3 border-l"
            style={{ borderColor: 'var(--border-color)' }}
          >
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center"
              style={{ background: 'var(--primary)' }}
            >
              <span className="text-white text-sm font-medium">
                {client.name?.[0]?.toUpperCase() || client.email?.[0]?.toUpperCase() || '?'}
              </span>
            </div>
            <span
              className="text-sm max-w-[120px] truncate"
              style={{ color: 'var(--text-secondary)' }}
            >
              {client.name || client.email}
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
