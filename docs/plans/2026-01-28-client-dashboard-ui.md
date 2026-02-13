# Client Dashboard UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a modern client-facing dashboard with project management, chat interface, and real-time activity log - separate from the existing admin UI.

**Architecture:** New React app mounted at `/client` route with project sidebar (left), chat panel (center), and collapsible activity log (right). Clients identified by email (looked up from GUID), can manage multiple projects. Backend extended with client-specific API endpoints.

**Tech Stack:** React 18, Tailwind CSS, Vite, FastAPI, WebSocket (existing), axios

---

## Phase 1: Backend API Extensions

### Task 1: Add Client API Endpoints to main.py

**Files:**
- Modify: `backend/main.py`

**Step 1: Add Pydantic models for client API**

Add after line ~20 (after existing imports):

```python
class ClientProjectCreate(BaseModel):
    email: str
    initial_request: str
    name: Optional[str] = None

class ClientProjectUpdate(BaseModel):
    name: Optional[str] = None
    archived: Optional[bool] = None
```

**Step 2: Add helper function to get sessions by email**

Add after `get_chat_history` function:

```python
def get_sessions_by_email(email: str) -> List[Dict]:
    """Get all sessions for a client email."""
    sessions = []
    if not ACTIVE_SESSIONS_DIR.exists():
        return sessions

    for session_path in ACTIVE_SESSIONS_DIR.iterdir():
        if not session_path.is_dir():
            continue
        status_file = session_path / "status.json"
        if not status_file.exists():
            continue
        try:
            status = json.loads(status_file.read_text())
            if status.get("email", "").lower() == email.lower():
                # Count messages
                chat_file = session_path / "chat_history.jsonl"
                message_count = 0
                if chat_file.exists():
                    message_count = sum(1 for _ in open(chat_file))

                # Get deployed URL if exists
                deployed_url = status.get("deployed_url")

                sessions.append({
                    "guid": session_path.name,
                    "name": status.get("client_name") or status.get("name") or f"Project {session_path.name[:8]}",
                    "email": status.get("email"),
                    "status": "deployed" if deployed_url else ("completed" if status.get("state") == "completed" else "active"),
                    "message_count": message_count,
                    "initial_request": status.get("initial_request", ""),
                    "deployed_url": deployed_url,
                    "archived": status.get("archived", False),
                    "created_at": status.get("created_at"),
                    "updated_at": status.get("updated_at")
                })
        except (json.JSONDecodeError, IOError):
            continue

    # Sort by updated_at descending
    sessions.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
    return sessions


def get_client_info_from_guid(guid: str) -> Optional[Dict]:
    """Get client info (email, name) from a session GUID."""
    session_path = ACTIVE_SESSIONS_DIR / guid
    status_file = session_path / "status.json"
    if not status_file.exists():
        return None
    try:
        status = json.loads(status_file.read_text())
        return {
            "email": status.get("email"),
            "name": status.get("client_name") or status.get("name"),
            "phone": status.get("phone")
        }
    except (json.JSONDecodeError, IOError):
        return None
```

**Step 3: Add GET /api/client/projects endpoint**

Add after existing admin endpoints:

```python
@app.get("/api/client/projects")
async def get_client_projects(email: str = None, guid: str = None):
    """Get all projects for a client (by email or lookup from guid)."""
    if not email and not guid:
        raise HTTPException(status_code=400, detail="Either email or guid required")

    if not email and guid:
        client_info = get_client_info_from_guid(guid)
        if not client_info or not client_info.get("email"):
            raise HTTPException(status_code=404, detail="Session not found or no email associated")
        email = client_info["email"]

    projects = get_sessions_by_email(email)
    client_info = get_client_info_from_guid(guid) if guid else None

    return {
        "success": True,
        "projects": projects,
        "client": client_info or {"email": email}
    }
```

**Step 4: Add POST /api/client/projects endpoint**

```python
@app.post("/api/client/projects")
async def create_client_project(data: ClientProjectCreate):
    """Create a new project for an existing client."""
    guid = generate_guid()

    try:
        initializer = SessionInitializer(
            guid=guid,
            email=data.email,
            initial_request=data.initial_request
        )
        await initializer.initialize()

        # Update name if provided
        if data.name:
            session_path = ACTIVE_SESSIONS_DIR / guid
            status_file = session_path / "status.json"
            if status_file.exists():
                status = json.loads(status_file.read_text())
                status["name"] = data.name
                status_file.write_text(json.dumps(status, indent=2))

        return {
            "success": True,
            "guid": guid,
            "link": f"/?guid={guid}&embed=true"
        }
    except Exception as e:
        logger.error(f"Failed to create client project: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Step 5: Add PATCH /api/client/projects/{guid} endpoint**

```python
@app.patch("/api/client/projects/{guid}")
async def update_client_project(guid: str, data: ClientProjectUpdate):
    """Update project properties (name, archived status)."""
    session_path = ACTIVE_SESSIONS_DIR / guid
    status_file = session_path / "status.json"

    if not status_file.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        status = json.loads(status_file.read_text())

        if data.name is not None:
            status["name"] = data.name
        if data.archived is not None:
            status["archived"] = data.archived

        status["updated_at"] = datetime.now().isoformat()
        status_file.write_text(json.dumps(status, indent=2))

        return {"success": True, "guid": guid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Step 6: Add POST /api/client/projects/{guid}/duplicate endpoint**

```python
@app.post("/api/client/projects/{guid}/duplicate")
async def duplicate_client_project(guid: str):
    """Duplicate an existing project."""
    session_path = ACTIVE_SESSIONS_DIR / guid
    status_file = session_path / "status.json"

    if not status_file.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        status = json.loads(status_file.read_text())
        email = status.get("email")
        initial_request = status.get("initial_request", "")
        original_name = status.get("name", "Project")

        if not email:
            raise HTTPException(status_code=400, detail="Original project has no email")

        # Create new project
        new_guid = generate_guid()
        initializer = SessionInitializer(
            guid=new_guid,
            email=email,
            initial_request=initial_request
        )
        await initializer.initialize()

        # Update name to indicate it's a copy
        new_session_path = ACTIVE_SESSIONS_DIR / new_guid
        new_status_file = new_session_path / "status.json"
        if new_status_file.exists():
            new_status = json.loads(new_status_file.read_text())
            new_status["name"] = f"{original_name} (Copy)"
            new_status_file.write_text(json.dumps(new_status, indent=2))

        return {
            "success": True,
            "guid": new_guid,
            "link": f"/?guid={new_guid}&embed=true"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Step 7: Run backend to verify endpoints**

Run: `cd backend && python -c "from main import app; print('Imports OK')"`
Expected: `Imports OK`

**Step 8: Commit backend changes**

```bash
git add backend/main.py
git commit -m "feat(api): add client project management endpoints"
```

---

## Phase 2: Frontend Foundation

### Task 2: Install Additional Dependencies

**Files:**
- Modify: `frontend/package.json`

**Step 1: Add required packages**

```bash
cd frontend && npm install react-icons lucide-react react-hot-toast
```

**Step 2: Verify installation**

Run: `cd frontend && npm list react-icons lucide-react react-hot-toast`
Expected: Shows installed versions

**Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add react-icons, lucide-react, react-hot-toast"
```

---

### Task 3: Create Theme Context and Hook

**Files:**
- Create: `frontend/src/client/hooks/useTheme.js`
- Create: `frontend/src/client/context/ThemeContext.jsx`

**Step 1: Create hooks directory**

```bash
mkdir -p frontend/src/client/hooks frontend/src/client/context
```

**Step 2: Create useTheme hook**

Create `frontend/src/client/hooks/useTheme.js`:

```javascript
import { useState, useEffect } from 'react';

export function useTheme() {
  const [theme, setTheme] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('client-theme') || 'dark';
    }
    return 'dark';
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('client-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  return { theme, setTheme, toggleTheme };
}
```

**Step 3: Create ThemeContext**

Create `frontend/src/client/context/ThemeContext.jsx`:

```javascript
import { createContext, useContext } from 'react';
import { useTheme } from '../hooks/useTheme';

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const themeState = useTheme();

  return (
    <ThemeContext.Provider value={themeState}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useThemeContext() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useThemeContext must be used within ThemeProvider');
  }
  return context;
}
```

**Step 4: Commit**

```bash
git add frontend/src/client/
git commit -m "feat(client): add theme context and hook"
```

---

### Task 4: Create Client API Service

**Files:**
- Create: `frontend/src/client/services/clientApi.js`

**Step 1: Create services directory**

```bash
mkdir -p frontend/src/client/services
```

**Step 2: Create client API service**

Create `frontend/src/client/services/clientApi.js`:

```javascript
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const clientApi = {
  // Get all projects for a client
  async getProjects(email = null, guid = null) {
    const params = new URLSearchParams();
    if (email) params.append('email', email);
    if (guid) params.append('guid', guid);
    const response = await api.get(`/api/client/projects?${params}`);
    return response.data;
  },

  // Create a new project
  async createProject(email, initialRequest, name = null) {
    const response = await api.post('/api/client/projects', {
      email,
      initial_request: initialRequest,
      name,
    });
    return response.data;
  },

  // Update project (rename, archive)
  async updateProject(guid, updates) {
    const response = await api.patch(`/api/client/projects/${guid}`, updates);
    return response.data;
  },

  // Duplicate a project
  async duplicateProject(guid) {
    const response = await api.post(`/api/client/projects/${guid}/duplicate`);
    return response.data;
  },

  // Get chat history for a project
  async getChatHistory(guid) {
    const response = await api.get(`/api/history?guid=${guid}`);
    return response.data;
  },

  // Send a message
  async sendMessage(guid, message) {
    const response = await api.post('/api/chat', { guid, message });
    return response.data;
  },
};

export default clientApi;
```

**Step 3: Commit**

```bash
git add frontend/src/client/services/
git commit -m "feat(client): add client API service"
```

---

### Task 5: Create useClientSession Hook

**Files:**
- Create: `frontend/src/client/hooks/useClientSession.js`

**Step 1: Create the hook**

Create `frontend/src/client/hooks/useClientSession.js`:

```javascript
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
```

**Step 2: Commit**

```bash
git add frontend/src/client/hooks/
git commit -m "feat(client): add useClientSession hook"
```

---

## Phase 3: Client UI Components

### Task 6: Create ThemeToggle Component

**Files:**
- Create: `frontend/src/client/components/ThemeToggle.jsx`

**Step 1: Create components directory**

```bash
mkdir -p frontend/src/client/components
```

**Step 2: Create ThemeToggle component**

Create `frontend/src/client/components/ThemeToggle.jsx`:

```javascript
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
```

**Step 3: Commit**

```bash
git add frontend/src/client/components/
git commit -m "feat(client): add ThemeToggle component"
```

---

### Task 7: Create Header Component

**Files:**
- Create: `frontend/src/client/components/Header.jsx`

**Step 1: Create Header component**

Create `frontend/src/client/components/Header.jsx`:

```javascript
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
```

**Step 2: Commit**

```bash
git add frontend/src/client/components/Header.jsx
git commit -m "feat(client): add Header component"
```

---

### Task 8: Create ProjectCard Component

**Files:**
- Create: `frontend/src/client/components/ProjectCard.jsx`

**Step 1: Create ProjectCard component**

Create `frontend/src/client/components/ProjectCard.jsx`:

```javascript
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

function getStatusIcon(status) {
  switch (status) {
    case 'deployed':
      return <ExternalLink className="w-3 h-3 text-green-500" />;
    case 'completed':
      return <CheckCircle className="w-3 h-3 text-blue-500" />;
    case 'active':
      return <Loader className="w-3 h-3 text-yellow-500 animate-spin" />;
    default:
      return <Circle className="w-3 h-3 text-gray-400" />;
  }
}

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
      className={`p-3 rounded-lg cursor-pointer transition-all border
        ${isActive
          ? 'dark:bg-indigo-500/20 dark:border-indigo-500/50 bg-indigo-50 border-indigo-200'
          : 'dark:bg-[#1a1a24] dark:border-gray-800 dark:hover:bg-[#1e1e2a] bg-white border-gray-200 hover:bg-gray-50'
        }`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${getStatusColor(project.status)}`} />
          <h3 className="font-medium text-sm truncate dark:text-white text-gray-900">
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
            className="p-1 rounded hover:bg-black/10 dark:hover:bg-white/10"
          >
            <MoreHorizontal className="w-4 h-4 dark:text-gray-400 text-gray-500" />
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
              <div className="absolute right-0 top-full mt-1 z-20 w-40 py-1 rounded-lg shadow-lg border
                dark:bg-[#1a1a24] dark:border-gray-700 bg-white border-gray-200">
                <button
                  onClick={(e) => handleMenuAction(onRename, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2
                    dark:hover:bg-gray-800 hover:bg-gray-100 dark:text-gray-300 text-gray-700"
                >
                  <Pencil className="w-3.5 h-3.5" /> Rename
                </button>
                <button
                  onClick={(e) => handleMenuAction(onDuplicate, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2
                    dark:hover:bg-gray-800 hover:bg-gray-100 dark:text-gray-300 text-gray-700"
                >
                  <Copy className="w-3.5 h-3.5" /> Duplicate
                </button>
                <button
                  onClick={(e) => handleMenuAction(onShare, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2
                    dark:hover:bg-gray-800 hover:bg-gray-100 dark:text-gray-300 text-gray-700"
                >
                  <Share2 className="w-3.5 h-3.5" /> Share
                </button>
                <button
                  onClick={(e) => handleMenuAction(onDownload, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2
                    dark:hover:bg-gray-800 hover:bg-gray-100 dark:text-gray-300 text-gray-700"
                >
                  <Download className="w-3.5 h-3.5" /> Download
                </button>
                <hr className="my-1 dark:border-gray-700 border-gray-200" />
                <button
                  onClick={(e) => handleMenuAction(onArchive, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2
                    dark:hover:bg-gray-800 hover:bg-gray-100 dark:text-gray-300 text-gray-700"
                >
                  <Archive className="w-3.5 h-3.5" /> Archive
                </button>
                <button
                  onClick={(e) => handleMenuAction(onDelete, e)}
                  className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2 text-red-500
                    dark:hover:bg-gray-800 hover:bg-gray-100"
                >
                  <Trash2 className="w-3.5 h-3.5" /> Delete
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Description snippet */}
      <p className="text-xs dark:text-gray-400 text-gray-500 truncate mb-2">
        {project.initial_request || 'No description'}
      </p>

      {/* Footer row */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-3 dark:text-gray-500 text-gray-400">
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
```

**Step 2: Commit**

```bash
git add frontend/src/client/components/ProjectCard.jsx
git commit -m "feat(client): add ProjectCard component"
```

---

### Task 9: Create ProjectSidebar Component

**Files:**
- Create: `frontend/src/client/components/ProjectSidebar.jsx`

**Step 1: Create ProjectSidebar component**

Create `frontend/src/client/components/ProjectSidebar.jsx`:

```javascript
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
```

**Step 2: Commit**

```bash
git add frontend/src/client/components/ProjectSidebar.jsx
git commit -m "feat(client): add ProjectSidebar component"
```

---

### Task 10: Create NewProjectModal Component

**Files:**
- Create: `frontend/src/client/components/NewProjectModal.jsx`

**Step 1: Create NewProjectModal component**

Create `frontend/src/client/components/NewProjectModal.jsx`:

```javascript
import { useState } from 'react';
import { X, Sparkles } from 'lucide-react';

const QUICK_STARTS = [
  { label: 'Landing Page', icon: '🎨', prompt: 'Build me a beautiful landing page with hero, features, pricing, and testimonials sections' },
  { label: 'Dashboard', icon: '📊', prompt: 'Create an admin dashboard with charts, tables, and sidebar navigation' },
  { label: 'API Backend', icon: '⚡', prompt: 'Build a REST API backend with authentication, CRUD operations, and database integration' },
  { label: 'Mobile App', icon: '📱', prompt: 'Create a mobile-responsive web app with native-like navigation and gestures' },
];

export function NewProjectModal({ isOpen, onClose, onCreate }) {
  const [request, setRequest] = useState('');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!request.trim()) return;

    setLoading(true);
    try {
      await onCreate(request.trim());
      setRequest('');
      onClose();
    } catch (err) {
      console.error('Failed to create project:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleQuickStart = (prompt) => {
    setRequest(prompt);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-lg rounded-xl shadow-2xl border
        dark:bg-[#1a1a24] dark:border-gray-700 bg-white border-gray-200">

        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b
          dark:border-gray-700 border-gray-200">
          <h2 className="text-lg font-semibold dark:text-white text-gray-900">
            Start New Project
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg dark:hover:bg-gray-700 hover:bg-gray-100"
          >
            <X className="w-5 h-5 dark:text-gray-400 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Text input */}
          <div>
            <label className="block text-sm font-medium mb-2 dark:text-gray-300 text-gray-700">
              What do you want to build?
            </label>
            <textarea
              value={request}
              onChange={(e) => setRequest(e.target.value)}
              placeholder="Describe your project in detail..."
              rows={4}
              className="w-full px-3 py-2 text-sm rounded-lg border resize-none
                dark:bg-[#12121a] dark:border-gray-700 dark:text-white dark:placeholder-gray-500
                bg-gray-50 border-gray-200 text-gray-900 placeholder-gray-400
                focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              autoFocus
            />
          </div>

          {/* Quick starts */}
          <div>
            <label className="block text-sm font-medium mb-2 dark:text-gray-300 text-gray-700">
              Quick starts
            </label>
            <div className="grid grid-cols-2 gap-2">
              {QUICK_STARTS.map((qs) => (
                <button
                  key={qs.label}
                  type="button"
                  onClick={() => handleQuickStart(qs.prompt)}
                  className="p-3 text-left rounded-lg border transition-colors
                    dark:border-gray-700 dark:hover:border-indigo-500/50 dark:hover:bg-indigo-500/10
                    border-gray-200 hover:border-indigo-300 hover:bg-indigo-50"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{qs.icon}</span>
                    <span className="text-sm font-medium dark:text-white text-gray-900">
                      {qs.label}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium rounded-lg
                dark:text-gray-300 dark:hover:bg-gray-700
                text-gray-700 hover:bg-gray-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!request.trim() || loading}
              className="px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2
                bg-indigo-500 hover:bg-indigo-600 text-white
                disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Sparkles className="w-4 h-4" />
              {loading ? 'Creating...' : 'Create Project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/client/components/NewProjectModal.jsx
git commit -m "feat(client): add NewProjectModal component"
```

---

### Task 11: Create CodeBlock Component

**Files:**
- Create: `frontend/src/client/components/CodeBlock.jsx`

**Step 1: Create CodeBlock component**

Create `frontend/src/client/components/CodeBlock.jsx`:

```javascript
import { useState } from 'react';
import { Copy, Check } from 'lucide-react';

export function CodeBlock({ children, className = '' }) {
  const [copied, setCopied] = useState(false);

  // Extract language from className (e.g., "language-javascript")
  const match = /language-(\w+)/.exec(className);
  const language = match ? match[1] : '';

  const handleCopy = async () => {
    const code = typeof children === 'string' ? children : children?.props?.children || '';
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group my-3">
      {/* Language badge */}
      {language && (
        <div className="absolute top-0 left-4 px-2 py-0.5 text-xs rounded-b
          dark:bg-gray-700 dark:text-gray-400 bg-gray-200 text-gray-600">
          {language}
        </div>
      )}

      {/* Copy button */}
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity
          dark:bg-gray-700 dark:hover:bg-gray-600 bg-gray-200 hover:bg-gray-300"
        title="Copy code"
      >
        {copied ? (
          <Check className="w-4 h-4 text-green-500" />
        ) : (
          <Copy className="w-4 h-4 dark:text-gray-400 text-gray-600" />
        )}
      </button>

      {/* Code block */}
      <pre className={`p-4 pt-8 rounded-lg overflow-x-auto text-sm
        dark:bg-[#0d0d12] dark:text-gray-300
        bg-gray-100 text-gray-800
        ${className}`}
      >
        <code>{children}</code>
      </pre>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/client/components/CodeBlock.jsx
git commit -m "feat(client): add CodeBlock component with copy functionality"
```

---

### Task 12: Create MessageBubble Component

**Files:**
- Create: `frontend/src/client/components/MessageBubble.jsx`

**Step 1: Create MessageBubble component**

Create `frontend/src/client/components/MessageBubble.jsx`:

```javascript
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CodeBlock } from './CodeBlock';
import { User, Bot, ExternalLink } from 'lucide-react';

function formatTime(timestamp) {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function MessageBubble({ message }) {
  const isUser = message.role === 'user';
  const isDeployment = message.content?.toLowerCase().includes('deployed:') ||
                       message.type === 'deployed';

  // Extract deployed URL if present
  const deployUrlMatch = message.content?.match(/https?:\/\/[^\s]+/);
  const deployUrl = isDeployment ? deployUrlMatch?.[0] : null;

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
        ${isUser
          ? 'bg-indigo-500'
          : 'dark:bg-gray-700 bg-gray-200'
        }`}
      >
        {isUser ? (
          <User className="w-4 h-4 text-white" />
        ) : (
          <Bot className="w-4 h-4 dark:text-gray-300 text-gray-600" />
        )}
      </div>

      {/* Message content */}
      <div className={`flex-1 max-w-[80%] ${isUser ? 'text-right' : ''}`}>
        {/* Header */}
        <div className={`flex items-center gap-2 mb-1 text-xs
          dark:text-gray-500 text-gray-400
          ${isUser ? 'justify-end' : ''}`}
        >
          <span className="font-medium">
            {isUser ? 'You' : 'Claude'}
          </span>
          <span>{formatTime(message.timestamp)}</span>
        </div>

        {/* Content bubble */}
        <div className={`rounded-2xl px-4 py-3 inline-block text-left
          ${isUser
            ? 'bg-indigo-500 text-white rounded-tr-sm'
            : isDeployment
              ? 'dark:bg-green-500/20 dark:border-green-500/30 bg-green-50 border border-green-200 rounded-tl-sm'
              : 'dark:bg-[#1a1a24] dark:text-gray-200 bg-gray-100 text-gray-800 rounded-tl-sm'
          }`}
        >
          {isDeployment && deployUrl ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-green-500 dark:text-green-400">
                <ExternalLink className="w-4 h-4" />
                <span className="font-medium">Deployed Successfully!</span>
              </div>

              {/* Preview placeholder */}
              <div className="w-full h-32 rounded-lg bg-gray-800/50 flex items-center justify-center
                border dark:border-gray-700 border-gray-300">
                <span className="text-sm dark:text-gray-400 text-gray-500">Preview</span>
              </div>

              {/* Link */}
              <a
                href={deployUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                {deployUrl}
              </a>
            </div>
          ) : (
            <div className={`prose prose-sm max-w-none
              ${isUser
                ? 'prose-invert'
                : 'dark:prose-invert'
              }`}
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ node, inline, className, children, ...props }) {
                    if (inline) {
                      return (
                        <code
                          className="px-1.5 py-0.5 rounded text-sm
                            dark:bg-gray-700 dark:text-gray-200
                            bg-gray-200 text-gray-800"
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    }
                    return (
                      <CodeBlock className={className}>
                        {children}
                      </CodeBlock>
                    );
                  },
                  a({ href, children }) {
                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-indigo-400 hover:text-indigo-300 underline"
                      >
                        {children}
                      </a>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/client/components/MessageBubble.jsx
git commit -m "feat(client): add MessageBubble component with markdown support"
```

---

### Task 13: Create ChatPanel Component

**Files:**
- Create: `frontend/src/client/components/ChatPanel.jsx`

**Step 1: Create ChatPanel component**

Create `frontend/src/client/components/ChatPanel.jsx`:

```javascript
import { useState, useRef, useEffect } from 'react';
import { Send, Paperclip, Mic, Loader, MoreHorizontal } from 'lucide-react';
import { MessageBubble } from './MessageBubble';

export function ChatPanel({
  project,
  messages,
  loading,
  onSendMessage,
  onProjectAction
}) {
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    onSendMessage(input.trim());
    setInput('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleVoiceInput = () => {
    // Placeholder for voice input
    setIsRecording(!isRecording);
    // TODO: Implement Web Speech API
  };

  return (
    <div className="flex-1 flex flex-col min-w-0
      dark:bg-[#0a0a0f] bg-white">

      {/* Header */}
      {project && (
        <div className="h-14 px-4 flex items-center justify-between border-b
          dark:border-gray-800 border-gray-200">
          <div className="min-w-0">
            <h2 className="font-semibold truncate dark:text-white text-gray-900">
              {project.name}
            </h2>
            <p className="text-xs dark:text-gray-500 text-gray-400">
              Started {new Date(project.created_at).toLocaleDateString()} • {project.message_count || 0} messages
            </p>
          </div>
          <button
            onClick={onProjectAction}
            className="p-2 rounded-lg dark:hover:bg-gray-800 hover:bg-gray-100"
          >
            <MoreHorizontal className="w-5 h-5 dark:text-gray-400 text-gray-500" />
          </button>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex-1 flex items-center justify-center h-full">
            <div className="text-center dark:text-gray-500 text-gray-400">
              <p className="text-lg mb-2">No messages yet</p>
              <p className="text-sm">Start a conversation to begin building</p>
            </div>
          </div>
        ) : (
          messages.map((message, index) => (
            <MessageBubble key={index} message={message} />
          ))
        )}

        {/* Typing indicator */}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full dark:bg-gray-700 bg-gray-200
              flex items-center justify-center">
              <Loader className="w-4 h-4 dark:text-gray-400 text-gray-500 animate-spin" />
            </div>
            <div className="dark:bg-[#1a1a24] bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="p-4 border-t dark:border-gray-800 border-gray-200">
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          {/* Attachment button */}
          <button
            type="button"
            className="p-2 rounded-lg dark:hover:bg-gray-800 hover:bg-gray-100
              dark:text-gray-400 text-gray-500"
            title="Attach file"
          >
            <Paperclip className="w-5 h-5" />
          </button>

          {/* Text input */}
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message..."
              rows={1}
              disabled={loading}
              className="w-full px-4 py-3 text-sm rounded-xl border resize-none
                dark:bg-[#1a1a24] dark:border-gray-700 dark:text-white dark:placeholder-gray-500
                bg-gray-50 border-gray-200 text-gray-900 placeholder-gray-400
                focus:outline-none focus:ring-2 focus:ring-indigo-500/50
                disabled:opacity-50"
            />
          </div>

          {/* Voice button */}
          <button
            type="button"
            onClick={handleVoiceInput}
            className={`p-2 rounded-lg transition-colors
              ${isRecording
                ? 'bg-red-500 text-white'
                : 'dark:hover:bg-gray-800 hover:bg-gray-100 dark:text-gray-400 text-gray-500'
              }`}
            title="Voice input"
          >
            <Mic className="w-5 h-5" />
          </button>

          {/* Send button */}
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="p-3 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white
              disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </form>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/client/components/ChatPanel.jsx
git commit -m "feat(client): add ChatPanel component"
```

---

### Task 14: Create ActivityPanel Component

**Files:**
- Create: `frontend/src/client/components/ActivityPanel.jsx`

**Step 1: Create ActivityPanel component**

Create `frontend/src/client/components/ActivityPanel.jsx`:

```javascript
import { useState, useEffect, useRef } from 'react';
import {
  ChevronRight,
  ChevronLeft,
  CheckCircle,
  AlertCircle,
  Loader,
  FileText,
  Rocket
} from 'lucide-react';

function getEventIcon(type) {
  switch (type) {
    case 'ack':
      return <CheckCircle className="w-3.5 h-3.5 text-green-500" />;
    case 'error':
      return <AlertCircle className="w-3.5 h-3.5 text-red-500" />;
    case 'file_created':
    case 'file_modified':
      return <FileText className="w-3.5 h-3.5 text-blue-500" />;
    case 'deployed':
      return <Rocket className="w-3.5 h-3.5 text-green-500" />;
    case 'done':
    case 'summary':
      return <CheckCircle className="w-3.5 h-3.5 text-green-500" />;
    default:
      return <Loader className="w-3.5 h-3.5 text-yellow-500 animate-spin" />;
  }
}

function formatTime(timestamp) {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

export function ActivityPanel({
  logs = [],
  progress = 0,
  statusMessage = '',
  connected = false,
  collapsed = false,
  onToggleCollapse
}) {
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll) {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  if (collapsed) {
    return (
      <div className="w-12 flex flex-col items-center py-4 border-l
        dark:bg-[#12121a] dark:border-gray-800 bg-gray-50 border-gray-200">
        <button
          onClick={onToggleCollapse}
          className="p-2 rounded-lg dark:hover:bg-gray-800 hover:bg-gray-100
            dark:text-gray-400 text-gray-500"
          title="Expand activity log"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>

        {/* Mini progress indicator */}
        {progress > 0 && progress < 100 && (
          <div className="mt-4 w-6 h-6 relative">
            <svg className="w-6 h-6 -rotate-90">
              <circle
                cx="12"
                cy="12"
                r="10"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="dark:text-gray-700 text-gray-200"
              />
              <circle
                cx="12"
                cy="12"
                r="10"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeDasharray={`${progress * 0.628} 62.8`}
                className="text-indigo-500"
              />
            </svg>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="w-80 flex flex-col border-l
      dark:bg-[#12121a] dark:border-gray-800 bg-gray-50 border-gray-200">

      {/* Header */}
      <div className="h-14 px-4 flex items-center justify-between border-b
        dark:border-gray-800 border-gray-200">
        <div className="flex items-center gap-2">
          <span className="font-semibold dark:text-white text-gray-900">Activity</span>
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
        </div>
        <button
          onClick={onToggleCollapse}
          className="p-2 rounded-lg dark:hover:bg-gray-800 hover:bg-gray-100
            dark:text-gray-400 text-gray-500"
          title="Collapse"
        >
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>

      {/* Progress bar */}
      {(progress > 0 || statusMessage) && (
        <div className="px-4 py-3 border-b dark:border-gray-800 border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm dark:text-gray-400 text-gray-600">Progress</span>
            <span className="text-sm font-medium dark:text-white text-gray-900">{progress}%</span>
          </div>
          <div className="h-2 rounded-full dark:bg-gray-700 bg-gray-200 overflow-hidden">
            <div
              className="h-full bg-indigo-500 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          {statusMessage && (
            <p className="mt-2 text-xs dark:text-gray-500 text-gray-400 truncate">
              {statusMessage}
            </p>
          )}
        </div>
      )}

      {/* Logs */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {logs.length === 0 ? (
          <div className="text-center py-8 dark:text-gray-500 text-gray-400 text-sm">
            No activity yet
          </div>
        ) : (
          logs.map((log, index) => (
            <div
              key={index}
              className="flex gap-2 text-xs"
            >
              <span className="dark:text-gray-600 text-gray-400 font-mono whitespace-nowrap">
                {formatTime(log.timestamp)}
              </span>
              <div className="flex items-start gap-1.5 min-w-0">
                {getEventIcon(log.type)}
                <span className="dark:text-gray-300 text-gray-600 break-words">
                  {log.message || log.type}
                </span>
              </div>
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>

      {/* Auto-scroll toggle */}
      <div className="px-4 py-2 border-t dark:border-gray-800 border-gray-200">
        <label className="flex items-center gap-2 text-xs cursor-pointer">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="rounded border-gray-300 dark:border-gray-600
              text-indigo-500 focus:ring-indigo-500"
          />
          <span className="dark:text-gray-400 text-gray-500">Auto-scroll</span>
        </label>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/client/components/ActivityPanel.jsx
git commit -m "feat(client): add ActivityPanel component"
```

---

## Phase 4: Main Client App

### Task 15: Create ClientApp Main Component

**Files:**
- Create: `frontend/src/client/ClientApp.jsx`

**Step 1: Create ClientApp component**

Create `frontend/src/client/ClientApp.jsx`:

```javascript
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
```

**Step 2: Commit**

```bash
git add frontend/src/client/ClientApp.jsx
git commit -m "feat(client): add main ClientApp component"
```

---

### Task 16: Update App.jsx for Routing

**Files:**
- Modify: `frontend/src/App.jsx`

**Step 1: Update App.jsx with routing**

Replace contents of `frontend/src/App.jsx`:

```javascript
import { lazy, Suspense } from 'react';

// Lazy load client and admin views
const SplitChatView = lazy(() => import('./components/SplitChatView'));
const ClientApp = lazy(() => import('./client/ClientApp'));

function LoadingFallback() {
  return (
    <div className="h-screen flex items-center justify-center bg-gray-100 dark:bg-[#0a0a0f]">
      <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

function App() {
  // Check if we're on the client route
  const isClientRoute = window.location.pathname.startsWith('/client');

  return (
    <Suspense fallback={<LoadingFallback />}>
      {isClientRoute ? <ClientApp /> : <SplitChatView />}
    </Suspense>
  );
}

export default App;
```

**Step 2: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: add routing between client and admin views"
```

---

### Task 17: Update Tailwind Config for Dark Mode

**Files:**
- Modify: `frontend/tailwind.config.js`

**Step 1: Check and update tailwind config**

Read existing config first, then update if needed:

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {},
  },
  plugins: [],
}
```

**Step 2: Commit**

```bash
git add frontend/tailwind.config.js
git commit -m "chore: enable class-based dark mode in tailwind"
```

---

### Task 18: Add Index Export for Client Components

**Files:**
- Create: `frontend/src/client/index.js`

**Step 1: Create index export**

Create `frontend/src/client/index.js`:

```javascript
export { default as ClientApp } from './ClientApp';
export { ThemeProvider, useThemeContext } from './context/ThemeContext';
export { useTheme } from './hooks/useTheme';
export { useClientSession } from './hooks/useClientSession';
export { clientApi } from './services/clientApi';
```

**Step 2: Commit**

```bash
git add frontend/src/client/index.js
git commit -m "chore(client): add index exports"
```

---

## Phase 5: Testing & Polish

### Task 19: Test Backend API Endpoints

**Step 1: Start backend server**

Run: `cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
Expected: Server starts on port 8000

**Step 2: Test GET /api/client/projects endpoint**

Run: `curl "http://localhost:8000/api/client/projects?email=test@example.com"`
Expected: JSON response with `{"success": true, "projects": [...], "client": {...}}`

**Step 3: Create test documentation**

Document any issues or adjustments needed.

---

### Task 20: Test Frontend Client App

**Step 1: Start frontend dev server**

Run: `cd frontend && npm run dev`
Expected: Vite dev server starts

**Step 2: Open client route**

Navigate to: `http://localhost:5173/client?guid=<existing-guid>`
Expected: Client dashboard loads with projects sidebar, chat panel, activity log

**Step 3: Test theme toggle**

Click theme toggle button
Expected: UI switches between dark and light mode

**Step 4: Test project creation**

Click "New Project" → Enter description → Click "Create"
Expected: New project appears in sidebar, chat panel shows empty state

---

### Task 21: Final Commit and Tag

**Step 1: Final commit**

```bash
git add -A
git commit -m "feat: complete client dashboard UI implementation

- Add client API endpoints (GET/POST/PATCH projects)
- Create ClientApp with theme support
- Add ProjectSidebar with filtering and search
- Add ChatPanel with markdown rendering
- Add ActivityPanel (collapsible)
- Add NewProjectModal with quick starts
- Route /client to new UI, keep existing admin UI"
```

**Step 2: Create tag**

```bash
git tag -a v2.0.0-client-ui -m "Client Dashboard UI Release"
```

---

## Summary

This plan implements a complete client-facing dashboard with:

1. **Backend**: 5 new API endpoints for client project management
2. **Frontend**: 15+ new React components organized in `src/client/`
3. **Features**:
   - Multi-theme (dark/light) with toggle
   - Project sidebar with search, filter, actions
   - Chat panel with markdown, code highlighting, deploy previews
   - Collapsible activity log with real-time progress
   - New project modal with quick starts
4. **Routing**: `/client` for client UI, `/` for admin UI (unchanged)

Total: ~20 tasks, ~1500 lines of new code
