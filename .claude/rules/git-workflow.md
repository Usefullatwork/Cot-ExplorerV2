# Git Workflow

## Branching
- Feature branches only: `feature/description`, `fix/description`, `refactor/description`
- Never commit directly to main
- One logical change per commit

## Commits
- Use `-m` flag (HEREDOC can hang on Windows/MSYS)
- Imperative mood: "Add patient export" not "Added patient export"
- Stage files by name: `git add src/file.js src/other.js`
- NEVER use `git add .` or `git add -A` (risk of staging secrets, can timeout on large repos)

## Before Committing
- Run relevant tests
- Verify build succeeds (if applicable)
- Check for debug statements

## Commit Message Format
<type>: <short description>

Types: feat, fix, refactor, test, docs, chore, perf
