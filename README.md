# VELORA PC
A dark graphite/purple Windows Lua script workspace.

Features: multi-tab editor, Lua/Luau file open/save, chunked syntax highlighting, output console, local Lua execution when Lua is installed, and Windows executable packaging.

**Integration note:** this starter is a standalone editor/local Lua workspace. It does not inject into, attach to, or modify Bloxro or another process. Bloxro execution requires an authorised interface or source-level integration.

## Build on Windows
Install Python 3.11+ and run `build_windows.bat`. The executable appears at `dist\VELORA.exe`.

## Build using GitHub
Push this folder to a repository on branch `main`. The workflow builds `VELORA.exe`; download it from the successful Actions run's Artifacts section.
