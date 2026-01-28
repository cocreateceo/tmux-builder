import { useState } from 'react';
import { Plus, Search, Filter } from 'lucide-react';
import { ProjectCard } from './ProjectCard';

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'completed', label: 'Completed' },
  { value: 'deployed', label: 'Deployed' },
  { value: 'archived', label: 'Archived' },
];

export function ProjectSidebar({
  projects,
  currentGuid,
  onSelectProject,
  onNewProject,
  onRenameProject,
  onDuplicateProject,
  onArchiveProject,
  onDeleteProject,
  onShareProject,
  onDownloadProject,
}) {
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [showFilterMenu, setShowFilterMenu] = useState(false);

  // Filter projects
  const filteredProjects = projects.filter(project => {
    // Search filter
    if (search) {
      const searchLower = search.toLowerCase();
      const matchesSearch =
        project.name?.toLowerCase().includes(searchLower) ||
        project.initial_request?.toLowerCase().includes(searchLower);
      if (!matchesSearch) return false;
    }

    // Status filter
    if (filter === 'all') return !project.archived;
    if (filter === 'archived') return project.archived;
    return project.status === filter && !project.archived;
  });

  return (
    <aside className="w-72 h-full flex flex-col border-r
      dark:bg-[#12121a] dark:border-gray-800
      bg-gray-50 border-gray-200">

      {/* Header */}
      <div className="p-4 border-b dark:border-gray-800 border-gray-200">
        <h2 className="font-semibold dark:text-white text-gray-900 mb-3">
          My Projects
        </h2>

        {/* New Project Button */}
        <button
          onClick={onNewProject}
          className="w-full py-2 px-4 rounded-lg font-medium text-sm
            bg-indigo-500 hover:bg-indigo-600 text-white
            flex items-center justify-center gap-2 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Project
        </button>
      </div>

      {/* Search and Filter */}
      <div className="p-3 space-y-2 border-b dark:border-gray-800 border-gray-200">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4
            dark:text-gray-500 text-gray-400" />
          <input
            type="text"
            placeholder="Search projects..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border
              dark:bg-[#1a1a24] dark:border-gray-700 dark:text-white dark:placeholder-gray-500
              bg-white border-gray-200 text-gray-900 placeholder-gray-400
              focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
          />
        </div>

        {/* Filter */}
        <div className="relative">
          <button
            onClick={() => setShowFilterMenu(!showFilterMenu)}
            className="flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg
              dark:text-gray-400 dark:hover:bg-gray-800
              text-gray-600 hover:bg-gray-100"
          >
            <Filter className="w-3.5 h-3.5" />
            {FILTERS.find(f => f.value === filter)?.label}
          </button>

          {showFilterMenu && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setShowFilterMenu(false)}
              />
              <div className="absolute left-0 top-full mt-1 z-20 w-36 py-1 rounded-lg shadow-lg border
                dark:bg-[#1a1a24] dark:border-gray-700 bg-white border-gray-200">
                {FILTERS.map(f => (
                  <button
                    key={f.value}
                    onClick={() => {
                      setFilter(f.value);
                      setShowFilterMenu(false);
                    }}
                    className={`w-full px-3 py-1.5 text-left text-sm
                      dark:hover:bg-gray-800 hover:bg-gray-100
                      ${filter === f.value
                        ? 'dark:text-indigo-400 text-indigo-600'
                        : 'dark:text-gray-300 text-gray-700'
                      }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Project List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {filteredProjects.length === 0 ? (
          <div className="text-center py-8 dark:text-gray-500 text-gray-400 text-sm">
            {search || filter !== 'all'
              ? 'No matching projects'
              : 'No projects yet'}
          </div>
        ) : (
          filteredProjects.map(project => (
            <ProjectCard
              key={project.guid}
              project={project}
              isActive={project.guid === currentGuid}
              onClick={() => onSelectProject(project.guid)}
              onRename={() => onRenameProject(project.guid)}
              onDuplicate={() => onDuplicateProject(project.guid)}
              onArchive={() => onArchiveProject(project.guid)}
              onDelete={() => onDeleteProject(project.guid)}
              onShare={() => onShareProject(project.guid)}
              onDownload={() => onDownloadProject(project.guid)}
            />
          ))
        )}
      </div>
    </aside>
  );
}
