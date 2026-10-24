# RecycLink deployment notes

## Does the backend need hosting?

Yes. The browser application calls the API for login, listings, collections, inventory, analytics, image classification, and voice session setup. It also needs a persistent database. Hosting only the built frontend will leave those workflows unavailable.

This project includes a single-container deployment path: the container builds the React app, runs FastAPI, and serves both from one origin. Pair it with a managed PostgreSQL database and persistent file storage if uploaded files are retained in a future release. The current classifier stores classification metadata and hashes, not uploaded image bytes.

## Required production settings

- `DATABASE_URL`: PostgreSQL connection URL.
- `SECRET_KEY`: unique random secret with at least 32 characters.
- `APP_ENV=production`.
- `FRONTEND_ORIGIN`: the public site origin (same-origin deployment is recommended).
- `PORT`: supplied by most container hosts; defaults to 8000.

Optional integrations stay visibly unconfigured until set up: ElevenLabs needs its server-side API key and Agent ID; OSRM needs a suitable operator-managed routing endpoint; classification needs licensed training data and a trained checkpoint. Do not run the development seed script in production.

## Build locally

From this directory:

```sh
docker build -t recyclink .
docker run --rm -p 8000:8000 \
  -e APP_ENV=production \
  -e SECRET_KEY="replace-with-a-unique-random-secret-of-32-characters-or-more" \
  -e DATABASE_URL="postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE" \
  recyclink
```

The container applies Alembic migrations before starting. Configure database TLS according to the selected managed PostgreSQL provider. Before exposing a deployment publicly, configure backups, monitoring, allowed upload limits, and the provider's health check at `/api/v1/health/ready`.

The repository has no Git remote configured in this workspace, and no hosting provider credentials are available here, so this file does not claim that a public deployment has been created.
