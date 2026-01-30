import { useState, useEffect, useCallback, useRef } from 'react';
import clientApi from '../services/clientApi';

/**
 * Client Session Hook
 *
 * Scenarios:
 * 1. /client?guid=xxx - Existing client with project, load their data
 * 2. /client?email=xxx - Client identified by email, load their projects
 * 3. /client?guid=xxx&email=yyy - Both provided, use either
 * 4. /client (no params) - No client identified, show empty state
 * 5. After onboarding redirect - /client?guid=newGuid
 */
export function useClientSession() {
  // Parse URL params ONCE on mount using lazy initial state
  const [urlParams] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return {
      guid: params.get('guid'),
      email: params.get('email'),
    };
  });

  // Initialize state from URL params
  const [guid, setGuid] = useState(urlParams.guid);
  const [client, setClient] = useState(urlParams.email ? { email: urlParams.email } : null);
  const [projects, setProjects] = useState([]);
  const [currentProject, setCurrentProject] = useState(null);
  const [loading, setLoading] = useState(true); // Start as true since we load on mount
  const [error, setError] = useState(null);

  // Track mounted state to prevent state updates after unmount
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  // Fetch projects from API - stable function
  const fetchProjects = useCallback(async (email, targetGuid) => {
    if (!targetGuid && !email) {
      return { projects: [], client: null };
    }
    const data = await clientApi.getProjects(email, targetGuid);
    return data;
  }, []);

  // Initial load on mount
  useEffect(() => {
    const email = urlParams.email;
    const targetGuid = urlParams.guid;

    // No params - nothing to load
    if (!targetGuid && !email) {
      setLoading(false);
      return;
    }

    // Load projects
    setLoading(true);
    setError(null);

    fetchProjects(email, targetGuid)
      .then(data => {
        if (!mountedRef.current) return;

        setProjects(data.projects || []);

        // Set client info from response
        if (data.client) {
          setClient(data.client);
        } else if (email) {
          setClient({ email });
        }

        // Set current project
        const current = (data.projects || []).find(p => p.guid === targetGuid);
        setCurrentProject(current || null);
        setLoading(false);
      })
      .catch(err => {
        if (!mountedRef.current) return;
        setError(err.response?.data?.detail || err.message);
        setLoading(false);
      });
    // Only run on mount - urlParams is stable (from useState lazy init)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Select project from existing list (no API call needed)
  const selectProject = useCallback((projectGuid) => {
    const project = projects.find(p => p.guid === projectGuid);
    setGuid(projectGuid);
    setCurrentProject(project || null);

    // Update URL without page reload
    const url = new URL(window.location);
    url.searchParams.set('guid', projectGuid);
    window.history.pushState({}, '', url);
  }, [projects]);

  // Refresh projects list
  const refresh = useCallback(async () => {
    const email = client?.email || urlParams.email;
    const currentGuid = guid || urlParams.guid;

    if (!currentGuid && !email) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await fetchProjects(email, currentGuid);
      if (!mountedRef.current) return;

      setProjects(data.projects || []);

      if (data.client) {
        setClient(data.client);
      }

      const current = (data.projects || []).find(p => p.guid === currentGuid);
      setCurrentProject(current || null);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err.response?.data?.detail || err.message);
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [guid, client?.email, urlParams.email, urlParams.guid, fetchProjects]);

  // Create new project
  const createProject = useCallback(async (initialRequest, name = null) => {
    const email = client?.email || urlParams.email;
    if (!email) {
      throw new Error('No client email available. Please access with ?email=your@email.com or complete onboarding first.');
    }

    const data = await clientApi.createProject(email, initialRequest, name);

    // Refresh to get updated project list
    const refreshData = await fetchProjects(email, data.guid);
    if (!mountedRef.current) return data;

    setProjects(refreshData.projects || []);
    setGuid(data.guid);

    const newProject = (refreshData.projects || []).find(p => p.guid === data.guid);
    setCurrentProject(newProject || null);

    // Update URL
    const url = new URL(window.location);
    url.searchParams.set('guid', data.guid);
    window.history.pushState({}, '', url);

    return data;
  }, [client?.email, urlParams.email, fetchProjects]);

  // Update project
  const updateProject = useCallback(async (projectGuid, updates) => {
    await clientApi.updateProject(projectGuid, updates);
    await refresh();
  }, [refresh]);

  // Duplicate project
  const duplicateProject = useCallback(async (projectGuid) => {
    const data = await clientApi.duplicateProject(projectGuid);

    // Refresh and select new project
    const email = client?.email || urlParams.email;
    const refreshData = await fetchProjects(email, data.guid);
    if (!mountedRef.current) return data;

    setProjects(refreshData.projects || []);
    setGuid(data.guid);

    const newProject = (refreshData.projects || []).find(p => p.guid === data.guid);
    setCurrentProject(newProject || null);

    // Update URL
    const url = new URL(window.location);
    url.searchParams.set('guid', data.guid);
    window.history.pushState({}, '', url);

    return data;
  }, [client?.email, urlParams.email, fetchProjects]);

  return {
    guid: guid || urlParams.guid,  // Return URL guid if state not yet set
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
