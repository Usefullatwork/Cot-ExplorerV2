# Coding Style

## File Limits
- Max 500 lines per file (split if exceeding)
- Max 80 lines per function (extract helpers if exceeding)
- Max 3 levels of nesting (refactor with early returns)

## Naming
- **Python**: snake_case for variables, functions, modules
- **JavaScript**: camelCase for variables/functions, PascalCase for classes only
- **Database columns**: snake_case
- **Constants**: UPPER_SNAKE_CASE
- **Files**: snake_case for Python, camelCase for JS components, kebab-case for utilities

## Imports
- Python: stdlib, third-party, internal (blank line between groups)
- JS: ES modules only (`import/export`), group by external then internal

## Error Handling
- Always catch async errors (no unhandled promise rejections)
- Catch blocks must provide context, not just re-throw
- Never swallow errors silently (`catch (e) {}` is forbidden)
- Never expose stack traces in error responses

## Comments
- Only where logic is non-obvious
- No commented-out code (delete it, git has history)
- TODO format: `# TODO(username): description` (Python) or `// TODO(username): description` (JS)
