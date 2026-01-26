ow I understand the full architecture. Let me present the Complete Application Flow with Dual Channels in sections.                                                                         
                                                                                                                                                                                               
  ---                                                                                                                                                                                          
  Section 1: Overall Architecture                                                                                                                                                              
                                                                                                                                                                                               
  ┌─────────────────────────────────────────────────────────────────────────────────┐                                                                                                          
  │                           BROWSER (React UI)                                     │                                                                                                         
  │                                                                                  │                                                                                                         
  │   ┌──────────────────────────────────┐    ┌────────────────────────────────┐    │                                                                                                          
  │   │     useWebSocket (Channel 1)      │    │  useProgressSocket (Channel 2) │    │                                                                                                         
  │   │     Chat messages                 │    │  Real-time progress            │    │                                                                                                         
  │   │     ws://localhost:8000/ws/{guid} │    │  ws://localhost:8001/ws/{guid} │    │                                                                                                         
  │   └──────────────┬───────────────────┘    └──────────────┬─────────────────┘    │                                                                                                          
  └──────────────────┼───────────────────────────────────────┼──────────────────────┘                                                                                                          
                     │                                       │                                                                                                                                 
                     ▼                                       ▼                                                                                                                                 
  ┌──────────────────────────────────────┐    ┌────────────────────────────────────┐                                                                                                           
  │        FastAPI Backend               │    │      MCP Server (Python)           │                                                                                                           
  │        Port 8000                     │    │      Port 8001                     │                                                                                                           
  │                                      │    │                                    │                                                                                                           
  │  • Session lifecycle                 │    │  • Runs as subprocess of Claude    │                                                                                                           
  │  • Tmux management                   │    │  • stdio ↔ Claude CLI (MCP)        │                                                                                                           
  │  • Write prompt.txt                  │    │  • WebSocket ↔ UI (progress)       │                                                                                                           
  │  • Send instruction via tmux         │    │                                    │                                                                                                           
  │  • Receive final response            │    │  Tools Claude can call:            │                                                                                                           
  │                                      │    │  • notify_ack()                    │                                                                                                           
  └─────────────┬────────────────────────┘    │  • send_progress()                 │                                                                                                           
                │                             │  • send_status()                   │                                                                                                           
                │ tmux send-keys              │  • send_response()                 │                                                                                                           
                │                             │  • notify_complete()               │                                                                                                           
                ▼                             └────────────────┬───────────────────┘                                                                                                           
  ┌────────────────────────────────────────────────────────────┼───────────────────┐                                                                                                           
  │                            TMUX SESSION                    │                   │                                                                                                           
  │                                                            │ stdio (MCP)       │                                                                                                           
  │    ┌──────────────────────────────────────────────────────┼───────────────┐   │                                                                                                            
  │    │                     CLAUDE CLI                       ▼               │   │                                                                                                            
  │    │                                                                      │   │                                                                                                            
  │    │    Registered MCP server: tmux-progress                              │   │                                                                                                            
  │    │    (Claude auto-spawns server.py as subprocess)                      │   │                                                                                                            
  │    │                                                                      │   │                                                                                                            
  │    │    When processing, Claude calls MCP tools:                          │   │                                                                                                            
  │    │    → notify_ack(guid)        → MCP server broadcasts to UI           │   │                                                                                                            
  │    │    → send_progress(guid, 50) → MCP server broadcasts to UI           │   │                                                                                                            
  │    │    → send_response(guid, ..) → MCP server broadcasts to UI           │   │                                                                                                            
  │    │                                                                      │   │                                                                                                            
  │    └──────────────────────────────────────────────────────────────────────┘   │                                                                                                            
  └────────────────────────────────────────────────────────────────────────────────┘                                                                                                           
                                                                                                                                                                                               
  Key insight: When Claude CLI starts, it automatically spawns our MCP server as a child process and communicates via stdin/stdout. The MCP server also runs a WebSocket server to relay       
  progress to the UI.                                                                                                                                                                          
                                                                                                

                                                                                                Section 2: How Claude CLI Knows to Call MCP Tools                                                                                                                                            
                                                                                                                                                                                               
  The Answer: We tell Claude in the system prompt.                                                                                                                                             
                                                                                                                                                                                               
  When we send an instruction to Claude via tmux, we include instructions to use the MCP tools. Claude CLI automatically discovers the registered MCP server's tools and can call them.        
                                                                                                                                                                                               
  ---                                                                                                                                                                                          
  The Flow:                                                                                                                                                                                    
                                                                                                                                                                                               
  Step 1: One-time MCP Registration                                                                                                                                                            
  claude mcp add tmux-progress -- python3 /path/to/mcp_server/server.py                                                                                                                        
                                                                                                                                                                                               
  Step 2: When Claude CLI starts, it:                                                                                                                                                          
  1. Reads its MCP config                                                                                                                                                                      
  2. Spawns python3 server.py as subprocess                                                                                                                                                    
  3. Sends initialize and tools/list requests via stdio                                                                                                                                        
  4. Discovers available tools: notify_ack, send_progress, etc.                                                                                                                                
                                                                                                                                                                                               
  Step 3: When we send instruction via tmux, we include the GUID:                                                                                                                              
  Read the prompt from /path/prompt.txt.                                                                                                                                                       
                                                                                                                                                                                               
  IMPORTANT: Use your MCP tools to report progress:                                                                                                                                            
  1. Call notify_ack(guid="ef0b6b6e...") immediately                                                                                                                                           
  2. Call send_progress(guid="ef0b6b6e...", percent=X) as you work                                                                                                                             
  3. Call send_status(guid="ef0b6b6e...", message="...", phase="...") for updates                                                                                                              
  4. Call send_response(guid="ef0b6b6e...", content="...") with your response                                                                                                                  
  5. Call notify_complete(guid="ef0b6b6e...") when done                                                                                                                                        
                                                                                                                                                                                               
  Step 4: Claude sees the tools and follows instructions:                                                                                                                                      
  - Claude's tool list now includes our MCP tools                                                                                                                                              
  - Claude follows our instructions and calls them with the GUID we provided                                                                                                                   
  - Each tool call goes: Claude → stdio → MCP server → WebSocket → UI                                                                                                                          
                                                                                                                                                                                               
  ---                                                                                                                                                                                          
  Updated Instruction Template                                                                                                                                                                 
                                                                                                                                                                                               
  The session_controller.py instruction changes from:                                                                                                                                          
  # OLD (file-based)                                                                                                                                                                           
  instruction = f"Read {prompt_file}, create {ack_marker}, process, create {completed_marker}"                                                                                                 
                                                                                                                                                                                               
  To:                                                                                                                                                                                          
  # NEW (MCP-based)                                                                                                                                                                            
  instruction = f"""Read the user message from {prompt_file}.                                                                                                                                  
                                                                                                                                                                                               
  Use your MCP tools to communicate:                                                                                                                                                           
  1. notify_ack(guid="{guid}") - call immediately                                                                                                                                              
  2. send_progress(guid="{guid}", percent=N) - call periodically                                                                                                                               
  3. send_response(guid="{guid}", content="your response") - when done                                                                                                                         
  4. notify_complete(guid="{guid}") - final call                                                                                                                                               
  """                                                                                                                                                                                          
                                                                                                                                                                                               
  ---                                                                                                                                                                                          
  Does this answer how Claude knows to call the tools? The key is:                                                                                                                             
  1. Discovery: MCP protocol auto-discovers tools from registered servers                                                                                                                      
  2. Instruction: We explicitly tell Claude to use them with the GUID    

  