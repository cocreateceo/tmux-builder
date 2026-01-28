import { useState, useEffect, useCallback } from 'react';
import clientApi from '../services/clientApi';

export function useClientSession(initialGuid = null) {
  const [guid, setGuid] = useState(initialGuid);
  const [client, setClient] = useState(null);
  const [projects, setProjects] = useState([]);
  const [currentProject, setCurrentProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load projects when guid changes
  const loadProjects = useCallback(async () => {
    if (!guid) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await clientApi.getProjects(null, guid);
      setProjects(data.projects || []);
      setClient(data.client);

      // Set current project to the one matching guid
      const current = data.projects?.find(p => p.guid === guid);
      setCurrentProject(current || null);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  }, [guid]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  // Select a project
  const selectProject = useCallback((projectGuid) => {
    setGuid(projectGuid);
    const project = projects.find(p => p.guid === projectGuid);
    setCurrentProject(project || null);

    // Update URL without reload
    const url = new URL(window.location);
    url.searchParams.set('guid', projectGuid);
    window.history.pushState({}, '', url);
  }, [projects]);

  // Create new project
  const createProject = useCallback(async (initialRequest, name = null) => {
    if (!client?.email) {
      throw new Error('No client email available');
    }

    const data = await clientApi.createProject(client.email, initialRequest, name);
    await loadProjects();
    selectProject(data.guid);
    return data;
  }, [client, loadProjects, selectProject]);

  // Update project
  const updateProject = useCallback(async (projectGuid, updates) => {
    await clientApi.updateProject(projectGuid, updates);
    await loadProjects();
  }, [loadProjects]);

  // Duplicate project
  const duplicateProject = useCallback(async (projectGuid) => {
    const data = await clientApi.duplicateProject(projectGuid);
    await loadProjects();
    selectProject(data.guid);
    return data;
  }, [loadProjects, selectProject]);

  // Refresh projects
  const refresh = useCallback(() => {
    loadProjects();
  }, [loadProjects]);

  return {
    guid,
    client,
    projects,
    currentProject,
    loading,
    error,
    selectProject,
    createProject,
    updateProject,
    duplicateProject,
    refresh,
  };
}
