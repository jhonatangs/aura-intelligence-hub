# SYSTEM CONTEXT: Deterministic AI-Assisted Development Workflow

## 1. Core Philosophy
You are operating within a strictly parameterized, deterministic AI-assisted development environment. We do not use "vibe coding" or unstructured chat loops. All code generation, refactoring, and context handoffs are driven by the File System acting as an API. 

## 2. CLI Execution Router
The user orchestrates agents from the Zsh terminal using strict syntax: `<command> <harness> <model>` (e.g., `ais antigravity gemini-3.8-flash`). 
The router maps specific aliases to specific prompt files in the workspace:
* `ais` -> Uses `.ai/prompts/1-start.txt` (Starts a new feature/task)
* `aif` -> Uses `.ai/prompts/2-fix.txt` (Fixes bugs/errors)
* `aipr` -> Uses `.ai/prompts/3-ship.txt` (Prepares code for commit/PR)
* `aipause` -> Uses `.ai/prompts/4-pause.txt` (Saves context before stopping)
* `airesume` -> Uses `.ai/prompts/5-resume.txt` (Reloads context for a new agent)

## 3. Workspace Structure (.ai/ directory)
Every project contains an `.ai/` directory initialized from the `ai-workflow-template`. You must respect this structure:
* `.ai/context.md`: The absolute source of truth for the project's current state, architecture, and recent decisions.
* `.ai/todo.md`: The active checklist of pending, in-progress, and completed tasks.
* `.ai/rules/`: Contains quality gates (`01-global.md`, `02-python.md`, `03-data.md`, etc.). You must validate all generated code against these rules.
* `.ai/prompts/`: Contains the instructional prompts used by the CLI.

## 4. Your Responsibilities as the AI Agent
1. **Context First:** Before writing any code, always read `.ai/context.md` and `.ai/todo.md` if available.
2. **File System as API:** Do not output long snippets of code in the chat if you have tools to write directly to the file system. Apply the changes autonomously.
3. **State Management:** If you are completing a task, you MUST update `.ai/todo.md` to reflect the progress. If you are pausing or handing off to another agent, you MUST update `.ai/context.md` with the latest architectural decisions.
4. **Task Mutation Strict Syntax:** When updating `.ai/todo.md`, you MUST preserve the exact Markdown checklist format. 
   - Pending task: `- [ ] Task description`
   - Completed task: `- [x] Task description`
   - NEVER delete completed tasks, NEVER alter the numbering, and NEVER use custom tags like `[Done]` or `[Finished]`.
5. **Strict Compliance:** Adhere to the specific rules defined in the `.ai/rules/` directory based on the stack we are currently using.

## 5. Initialization Behavior
When entering a repository using this workflow:
1. Read `.ai/ai-workflow-guidelines.md`.
2. Read `.ai/context.md`.
3. Read `.ai/todo.md`.
4. Identify the current task.
5. Apply the relevant rules under `.ai/rules/`.
6. Follow the active workflow prompt under `.ai/prompts/`.
7. Begin execution without requiring an acknowledgment message.
