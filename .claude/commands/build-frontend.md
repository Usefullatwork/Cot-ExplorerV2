---
description: Build the frontend dashboard and verify output
allowed-tools: Bash, Read
---

Build and verify the Cot-ExplorerV2 frontend:

```bash
cd C:\Users\MadsF\Desktop\Cot-ExplorerV2\frontend && npm run build
```

Verify:
1. `dist/` directory exists with `index.html`
2. `dist/assets/` contains JS and CSS chunks
3. No build errors or warnings
4. Report total bundle size

If build fails, show the error output.
