import { Bell } from 'lucide-react';
import { ThemeToggle } from './ThemeToggle';

export function Header({ client, connected }) {
  return (
    <header className="h-14 px-4 flex items-center justify-between border-b
      dark:bg-[#12121a] dark:border-gray-800
      bg-white border-gray-200">

      {/* Logo */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-indigo-500 flex items-center justify-center">
          <span className="text-white font-bold text-sm">TB</span>
        </div>
        <span className="font-semibold dark:text-white text-gray-900">
          Tmux Builder
        </span>

        {/* Connection status */}
        <div className="flex items-center gap-1.5 ml-4">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-xs dark:text-gray-500 text-gray-400">
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3">
        {/* Notifications */}
        <button className="p-2 rounded-lg transition-colors relative
          dark:hover:bg-gray-800 hover:bg-gray-100
          dark:text-gray-400 text-gray-500">
          <Bell className="w-5 h-5" />
        </button>

        {/* Theme toggle */}
        <ThemeToggle />

        {/* User */}
        {client && (
          <div className="flex items-center gap-2 pl-3 border-l dark:border-gray-700 border-gray-200">
            <div className="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center">
              <span className="text-white text-sm font-medium">
                {client.name?.[0]?.toUpperCase() || client.email?.[0]?.toUpperCase() || '?'}
              </span>
            </div>
            <span className="text-sm dark:text-gray-300 text-gray-700 max-w-[120px] truncate">
              {client.name || client.email}
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
