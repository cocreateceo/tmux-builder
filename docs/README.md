# Documentation

This folder contains all project documentation for tmux-builder.

## Getting Started
- **[QUICKSTART.md](QUICKSTART.md)** - Quick setup and usage guide
- **[SETUP.md](SETUP.md)** - Detailed installation instructions

## Architecture & Design
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture overview
- **[SMARTBUILD_ARCHITECTURE_ANALYSIS.md](SMARTBUILD_ARCHITECTURE_ANALYSIS.md)** - Detailed SmartBuild pattern analysis
- **[HOW_TO_IMPLEMENT_TMUX_IN_ANY_PROJECT.md](HOW_TO_IMPLEMENT_TMUX_IN_ANY_PROJECT.md)** - Integration guide for other projects

## Project Status
- **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - High-level project overview
- **[PROJECT_STATUS.txt](PROJECT_STATUS.txt)** - Current status and progress
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Implementation details
- **[TEST_VALIDATION_REPORT.md](TEST_VALIDATION_REPORT.md)** - Test results and validation
- **[README_FINAL.md](README_FINAL.md)** - Final project documentation

## Key Features

### SmartBuild Pattern
tmux-builder implements a **file-based I/O pattern** that makes it LLM-friendly:
- No CLI prompts required during execution
- Input via JSON files in `sessions/active/<name>/prompts/`
- Output via text files in `sessions/active/<name>/output/`
- Fully automated workflow for AI-driven development

### Session Management
- Persistent tmux sessions for stateful conversations
- Automatic session creation and cleanup
- File-based communication for reliability

## Documentation Organization

All documentation files have been moved to this `docs/` folder to keep the root directory clean and organized.
