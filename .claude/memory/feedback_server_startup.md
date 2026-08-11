---
name: Don't start the server
description: User starts the server themselves; Claude should not run it
type: feedback
---

Never run the server (via `./run.sh`, `uvicorn`, or any other method). The user always starts it themselves.

**Why:** User preference — they want control over when the server starts.

**How to apply:** Skip any verification steps that require a running server. Describe how to test manually instead of running the server.
