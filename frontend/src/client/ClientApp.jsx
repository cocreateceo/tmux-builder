import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
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
import { initTheme } from '../themes/ThemeManager';
import '../themes/themeStyles.css';

function ClientAppContent() {
  const [activityCollapsed, setActivityCollapsed] = useState(false);
  const [showNewProjectModal, setShowNewProjectModal] = useState(false);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activityWidth, setActivityWidth] = useState(() => {
    const saved = localStorage.getItem('activityPanelWidth');
    return saved ? parseInt(saved, 10) : 400;
  });
  const [isResizing, setIsResizing] = useState(false);

  // Initialize ember theme on mount
  useEffect(() => {
    initTheme('ember');
  }, []);

  // useClientSession handles URL params internally - no need to pass initialGuid
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
  } = useClientSession();

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

  // Load chat history when guid changes
  useEffect(() => {
    if (!guid) {
      setMessages([]);
      return;
    }

    // Load history for this guid
    clientApi.getChatHistory(guid)
      .then(response => {
        if (response?.messages && Array.isArray(response.messages)) {
          setMessages(response.messages);
        } else {
          setMessages([]);
        }
      })
      .catch(err => {
        console.error('Failed to load chat history:', err);
        setMessages([]);
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
    } finally {
      // Always set loading to false when request completes
      setLoading(false);
    }
  }, [guid]);

  // File upload handler
  const handleFileUpload = useCallback(async (file) => {
    if (!guid) return;

    // Add user message indicating file upload
    setMessages(prev => [...prev, {
      role: 'user',
      content: `📎 Uploaded file: ${file.name}`,
      timestamp: new Date().toISOString()
    }]);
    setLoading(true);

    try {
      const response = await clientApi.uploadFile(guid, file);
      if (response.success) {
        toast.success('File uploaded! Building website...');
        // The backend will trigger Claude to process the file
        // Response will come through the normal message flow
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to upload file');
      setLoading(false);
    }
    // Note: loading will be set to false when Claude responds via WebSocket
  }, [guid]);

  // Project action handlers
  const handleSelectProject = useCallback((projectGuid) => {
    selectProject(projectGuid);
    clearActivityLog();
  }, [selectProject, clearActivityLog]);

  const handleCreateProject = useCallback(async (initialRequest, name) => {
    await createProject(initialRequest, name);
    toast.success('Project created!');
    clearActivityLog();
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

  // Resize handlers for activity panel
  const handleResizeStart = useCallback((e) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e) => {
      const newWidth = window.innerWidth - e.clientX;
      const clampedWidth = Math.max(280, Math.min(600, newWidth));
      setActivityWidth(clampedWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      localStorage.setItem('activityPanelWidth', activityWidth.toString());
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, activityWidth]);

  if (sessionLoading && !projects.length) {
    return (
      <div data-theme="ember" className="h-screen flex items-center justify-center">
        <div className="embed-background" />
        <div className="text-center relative z-10">
          <div className="w-8 h-8 border-2 border-[var(--primary)] border-t-transparent
            rounded-full animate-spin mx-auto mb-4" />
          <p className="text-[var(--text-muted)]">Loading your projects...</p>
        </div>
      </div>
    );
  }

  if (sessionError && !projects.length) {
    return (
      <div data-theme="ember" className="h-screen flex items-center justify-center">
        <div className="embed-background" />
        <div className="text-center relative z-10">
          <p className="text-red-500 mb-4">{sessionError}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-[var(--primary)] text-white rounded-lg"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div data-theme="ember" className={`h-screen flex flex-col ${isResizing ? 'select-none cursor-col-resize' : ''}`}>
      {/* Background image with ember overlay */}
      <div className="embed-background" />

      <Toaster
        position="top-right"
        toastOptions={{
          className: 'dark:bg-gray-800 dark:text-white',
        }}
      />

      <Header client={client} connected={connected} guid={guid} />

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
          client={client}
          onSendMessage={handleSendMessage}
          onFileUpload={handleFileUpload}
          onProjectAction={() => {}}
        />

        {/* Resizable divider */}
        {!activityCollapsed && (
          <div
            onMouseDown={handleResizeStart}
            className={`w-1 cursor-col-resize hover:bg-indigo-500/50 active:bg-indigo-500
              transition-colors ${isResizing ? 'bg-indigo-500' : 'dark:bg-gray-800 bg-gray-200'}`}
          />
        )}

        <ActivityPanel
          logs={activityLog}
          progress={progress}
          statusMessage={statusMessage}
          connected={connected}
          collapsed={activityCollapsed}
          onToggleCollapse={() => setActivityCollapsed(!activityCollapsed)}
          width={activityWidth}
        />
      </div>

      <NewProjectModal
        isOpen={showNewProjectModal}
        onClose={() => setShowNewProjectModal(false)}
        onCreate={handleCreateProject}
        client={client}
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
