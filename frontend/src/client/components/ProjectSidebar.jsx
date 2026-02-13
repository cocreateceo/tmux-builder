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
    <aside
      className="w-72 h-full flex flex-col border-r"
      style={{
        background: 'var(--bg-primary)',
        borderColor: 'var(--border-color)'
      }}
    >
      {/* Header */}
      <div className="p-4 border-b" style={{ borderColor: 'var(--border-color)' }}>
        <h2 className="font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
          My Projects
        </h2>

        {/* New Project Button */}
        <button
          onClick={onNewProject}
          className="w-full py-2 px-4 rounded-lg font-medium text-sm text-white
            flex items-center justify-center gap-2 transition-colors hover:opacity-90"
          style={{ background: 'var(--primary)' }}
        >
          <Plus className="w-4 h-4" />
          New Project
        </button>
      </div>

      {/* Search and Filter */}
      <div className="p-3 space-y-2 border-b" style={{ borderColor: 'var(--border-color)' }}>
        {/* Search */}
        <div className="relative">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
            style={{ color: 'var(--text-muted)' }}
          />
          <input
            type="text"
            placeholder="Search projects..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border focus:outline-none"
            style={{
              background: 'var(--bg-secondary)',
              borderColor: 'var(--border-color)',
              color: 'var(--text-primary)'
            }}
          />
        </div>

        {/* Filter */}
        <div className="relative">
          <button
            onClick={() => setShowFilterMenu(!showFilterMenu)}
            className="flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg hover:opacity-80"
            style={{ color: 'var(--text-muted)' }}
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
              <div
                className="absolute left-0 top-full mt-1 z-20 w-36 py-1 rounded-lg shadow-lg border"
                style={{
                  background: 'var(--bg-secondary)',
                  borderColor: 'var(--border-color)'
                }}
              >
                {FILTERS.map(f => (
                  <button
                    key={f.value}
                    onClick={() => {
                      setFilter(f.value);
                      setShowFilterMenu(false);
                    }}
                    className="w-full px-3 py-1.5 text-left text-sm hover:opacity-80"
                    style={{
                      color: filter === f.value ? 'var(--primary)' : 'var(--text-secondary)'
                    }}
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
          <div className="text-center py-8 text-sm" style={{ color: 'var(--text-muted)' }}>
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
