import { useState, useCallback, useMemo, useEffect } from 'react';
import { Toaster, toast } from 'react-hot-toast';
import { ThemeProvider } from './context/ThemeContext';
import { useClientSession } from './hooks/useClientSession';
import { useProgressSocket } from '../hooks/useProgressSocket';
import clientApi from './services/clientApi';
import { Header } from './components/Header';
import { ProjectSidebar } from './components/ProjectSidebar';
import { ChatPanel } from './components/ChatPanel';
import { ActivityPanel } from './components/ActivityPanel';
import { NewProjectModal } from './components/NewProjectModal';

function getUrlGuid() {
  const params = new URLSearchParams(window.location.search);
  return params.get('guid');
}

function ClientAppContent() {
  const initialGuid = getUrlGuid();
  const [activityCollapsed, setActivityCollapsed] = useState(false);
  const [showNewProjectModal, setShowNewProjectModal] = useState(false);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const {
    guid,
    client,
    projects,
    currentProject,
    loading: sessionLoading,
    error: sessionError,
    selectProject,
    createProject,
    updateProject,
    duplicateProject,
    refresh: refreshProjects,
  } = useClientSession(initialGuid);

  // WebSocket handlers for real-time updates
  const wsHandlers = useMemo(() => ({
    onSummary: (data) => {
      if (data.message) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.message,
          timestamp: data.timestamp
        }]);
      }
      setLoading(false);
    },
    onDeployed: (data) => {
      if (data.message) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: `Deployed: ${data.message}`,
          timestamp: data.timestamp,
          type: 'deployed'
        }]);
        toast.success('Deployment complete!');
        refreshProjects();
      }
    },
    onResponse: (data) => {
      const content = data.message || data.content;
      if (content) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content,
          timestamp: data.timestamp
        }]);
      }
      setLoading(false);
    },
    onError: (data) => {
      toast.error(data.message || 'An error occurred');
      setLoading(false);
    }
  }), [refreshProjects]);

  const {
    connected,
    progress,
    statusMessage,
    activityLog,
    clearActivityLog
  } = useProgressSocket(guid, wsHandlers);

  // Load chat history when project changes
  useEffect(() => {
    if (!guid) {
      setMessages([]);
      return;
    }

    clientApi.getChatHistory(guid)
      .then(response => {
        if (response?.messages) {
          setMessages(response.messages);
        }
      })
      .catch(err => {
        console.error('Failed to load history:', err);
      });
  }, [guid]);

  // Send message handler
  const handleSendMessage = useCallback(async (content) => {
    if (!guid) return;

    setMessages(prev => [...prev, {
      role: 'user',
      content,
      timestamp: new Date().toISOString()
    }]);
    setLoading(true);

    try {
      const response = await clientApi.sendMessage(guid, content);
      if (response.success && response.response) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: response.response,
          timestamp: response.timestamp || new Date().toISOString()
        }]);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message);
      setLoading(false);
    }
  }, [guid]);

  // Project action handlers
  const handleSelectProject = useCallback((projectGuid) => {
    selectProject(projectGuid);
    clearActivityLog();
  }, [selectProject, clearActivityLog]);

  const handleCreateProject = useCallback(async (initialRequest, name) => {
    try {
      await createProject(initialRequest, name);
      toast.success('Project created!');
      clearActivityLog();
    } catch (err) {
      toast.error(err.message || 'Failed to create project');
      throw err;
    }
  }, [createProject, clearActivityLog]);

  const handleRenameProject = useCallback(async (projectGuid) => {
    const project = projects.find(p => p.guid === projectGuid);
    const newName = window.prompt('Enter new project name:', project?.name || '');
    if (newName && newName !== project?.name) {
      try {
        await updateProject(projectGuid, { name: newName });
        toast.success('Project renamed');
      } catch (err) {
        toast.error('Failed to rename project');
      }
    }
  }, [projects, updateProject]);

  const handleDuplicateProject = useCallback(async (projectGuid) => {
    try {
      await duplicateProject(projectGuid);
      toast.success('Project duplicated');
    } catch (err) {
      toast.error('Failed to duplicate project');
    }
  }, [duplicateProject]);

  const handleArchiveProject = useCallback(async (projectGuid) => {
    if (!window.confirm('Archive this project?')) return;
    try {
      await updateProject(projectGuid, { archived: true });
      toast.success('Project archived');
    } catch (err) {
      toast.error('Failed to archive project');
    }
  }, [updateProject]);

  const handleDeleteProject = useCallback(async (projectGuid) => {
    if (!window.confirm('Delete this project? This cannot be undone.')) return;
    try {
      // For now, just archive - implement actual delete in backend if needed
      await updateProject(projectGuid, { archived: true });
      toast.success('Project deleted');
    } catch (err) {
      toast.error('Failed to delete project');
    }
  }, [updateProject]);

  const handleShareProject = useCallback((projectGuid) => {
    const url = `${window.location.origin}/client?guid=${projectGuid}`;
    navigator.clipboard.writeText(url);
    toast.success('Link copied to clipboard!');
  }, []);

  const handleDownloadProject = useCallback((projectGuid) => {
    toast('Download feature coming soon!', { icon: '🚧' });
  }, []);

  if (sessionLoading && !projects.length) {
    return (
      <div className="h-screen flex items-center justify-center
        dark:bg-[#0a0a0f] bg-gray-50">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent
            rounded-full animate-spin mx-auto mb-4" />
          <p className="dark:text-gray-400 text-gray-500">Loading your projects...</p>
        </div>
      </div>
    );
  }

  if (sessionError && !projects.length) {
    return (
      <div className="h-screen flex items-center justify-center
        dark:bg-[#0a0a0f] bg-gray-50">
        <div className="text-center">
          <p className="text-red-500 mb-4">{sessionError}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-indigo-500 text-white rounded-lg"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col dark:bg-[#0a0a0f] bg-gray-50">
      <Toaster
        position="top-right"
        toastOptions={{
          className: 'dark:bg-gray-800 dark:text-white',
        }}
      />

      <Header client={client} connected={connected} />

      <div className="flex-1 flex overflow-hidden">
        <ProjectSidebar
          projects={projects}
          currentGuid={guid}
          onSelectProject={handleSelectProject}
          onNewProject={() => setShowNewProjectModal(true)}
          onRenameProject={handleRenameProject}
          onDuplicateProject={handleDuplicateProject}
          onArchiveProject={handleArchiveProject}
          onDeleteProject={handleDeleteProject}
          onShareProject={handleShareProject}
          onDownloadProject={handleDownloadProject}
        />

        <ChatPanel
          project={currentProject}
          messages={messages}
          loading={loading}
          onSendMessage={handleSendMessage}
          onProjectAction={() => {}}
        />

        <ActivityPanel
          logs={activityLog}
          progress={progress}
          statusMessage={statusMessage}
          connected={connected}
          collapsed={activityCollapsed}
          onToggleCollapse={() => setActivityCollapsed(!activityCollapsed)}
        />
      </div>

      <NewProjectModal
        isOpen={showNewProjectModal}
        onClose={() => setShowNewProjectModal(false)}
        onCreate={handleCreateProject}
      />
    </div>
  );
}

export default function ClientApp() {
  return (
    <ThemeProvider>
      <ClientAppContent />
    </ThemeProvider>
  );
}
