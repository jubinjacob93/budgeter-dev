# Process

How work is organized in this project. Every agent session reads this before starting a task.

## Tasks

- The backlog is `_docs/tasks.md`. Work on one task at a time, in order, and only when every task under **Depends on** is done.
- A groomed task is saved as `_docs/tasks/NN-short-title.md` (e.g. `_docs/tasks/07-seed-special-scenarios.md`) using `_docs/task-template.md`.
- Read the acceptance criteria before starting a task and again before finishing it.
- When a task is done, add ✅ to its title in `_docs/tasks.md`.

## Roles

- **PM** - grooms a task before anyone implements it. Follows `_docs/team/pm.md`.
- **Engineer** - implements one groomed task. Follows `_docs/team/software-engineer.md`.
- **QA** - checks the result against the acceptance criteria. Follows `_docs/team/qa-engineer.md`.

Each role runs in a fresh session. The engineer never tests its own work as QA.

## Lifecycle

1. Pick the next task whose dependencies are done.
2. **PM** grooms it into `_docs/tasks/NN-short-title.md`.
3. **Human** reviews and corrects the groomed task.
4. **Engineer** implements it and commits.
5. **QA** adds a PASS or FAIL verdict to the bottom of the groomed task file.
6. On FAIL, go back to step 4 with the QA verdict as input.
7. On PASS, the **human** reviews the code and asks about anything unclear.
8. Mark the task ✅ in `_docs/tasks.md` and commit.

## Rules

- Do not skip grooming.
- The engineer does not change acceptance criteria. If one is wrong or impossible, the engineer notes it in the task file and stops.
- QA does not fix code. It only reports.
- Only the human marks a task done.
- Commit after every meaningful step. Commit messages reference the task number, e.g. `task 07: add refund scenarios`.
- Start a new session for each task and each role.

## Keeping documents current

When an agent needs correcting during a session, update the relevant document so the correction sticks:

```
Based on the corrections I made, find the relevant documents and update them.
Commit the current work before changing the documents.
```

## Later

- Tasks may move to GitHub Issues; if they do, issues replace `_docs/tasks.md` and the groomed task files.
- An orchestrator session may later run the lifecycle automatically, launching PM, Engineer and QA as subagents.
