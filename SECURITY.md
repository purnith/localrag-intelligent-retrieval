# Security

## Current Boundary

LocalRAG is designed for local development and private document retrieval. It includes authentication and server-side authorization, but production deployment requires additional hardening.

## Existing Controls

- Argon2 password hashing
- Signed HTTP-only session cookies
- User-scoped document access
- Server-side authorization checks
- `.env` and runtime data ignored by Git

## Data To Keep Out Of Git

- `.env`
- Uploaded documents
- Database files or dumps
- Ollama model data
- Redis/PostgreSQL volumes
- Production secrets

## Production Hardening Checklist

- Use a strong `JWT_SECRET`
- Set `COOKIE_SECURE=true`
- Terminate traffic with HTTPS
- Add login rate limiting
- Add password reset/email verification
- Add object storage encryption for uploaded files
- Configure database backups and retention policy
- Run dependency scanning in CI
- Add structured application logs and audit events

## Reporting Issues

For a personal portfolio deployment, report issues privately to the repository owner.

