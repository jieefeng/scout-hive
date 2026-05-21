# Backend Port Change: 8000 → 7007

## Summary

Change the backend server port from 8000 to 7007 across all configuration files, frontend API client, and startup script.

## Motivation

The user requested the backend run on port 7007 instead of the default 8000.

## Scope

4 files require modification:

| File | Line(s) | Current | Target |
|---|---|---|---|
| `backend/config.yaml` | 3 | `port: 8000` | `port: 7007` |
| `backend/app/config.py` | 40 | `port: int = 8000` | `port: int = 7007` |
| `frontend/src/api/client.ts` | 1-2 | `localhost:8000` | `localhost:7007` |
| `start.bat` | 10-11 | `--port 8000` | `--port 7007` |

## Approach

Direct string replacement in all 4 files. No architectural changes, no new dependencies.

## Out of Scope

- Environment variable-based port configuration (future enhancement)
- Vite proxy setup (not needed for this change)
- Production deployment configuration
