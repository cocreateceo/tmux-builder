import { Sun, Moon } from 'lucide-react';
import { useThemeContext } from '../context/ThemeContext';

export function ThemeToggle() {
  const { theme, toggleTheme } = useThemeContext();

  return (
    <button
      onClick={toggleTheme}
      className="p-2 rounded-lg transition-colors
        dark:bg-gray-800 dark:hover:bg-gray-700 dark:text-gray-300
        bg-gray-100 hover:bg-gray-200 text-gray-600"
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
    >
      {theme === 'dark' ? (
        <Sun className="w-5 h-5" />
      ) : (
        <Moon className="w-5 h-5" />
      )}
    </button>
  );
}
