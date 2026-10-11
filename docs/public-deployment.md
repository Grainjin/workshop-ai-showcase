# Public Demo deployment configuration

Use the repository root for the Railway API project, `frontend/mobile` for the
Vercel Demo project, and `showcase/site` for the separate Vercel Case Study project.
All hosts below are non-secret examples. Replace them with the provisioned URLs.

## Railway API

`railway.toml` builds `docker/api/Dockerfile`. Its pre-deploy `release` command only
runs Alembic migrations; a nonzero exit prevents deployment. Runtime `api` startup
binds to Railway's `PORT`, validates public settings, and does not migrate, seed,
reset, or generate replacement JWT keys. `/health` is dependency-free liveness.
The Docker image also probes this endpoint on `PORT` (default 8000 locally).

Provision these environment variables in Railway's private secret store:

```dotenv
WORKSHOP_PUBLIC_DEPLOYMENT=true
DEMO_MODE=true
WORKSHOP_PAYMENT_MODE=demo
WORKSHOP_CORS_ORIGINS=https://demo.example.com,https://case.example.com
WORKSHOP_DATABASE_URL=<private PostgreSQL URL using postgresql+psycopg://>
```

CORS values must be bare origins with no trailing slash, matching the browser's
`Origin` header exactly.

Provide a stable matching RSA PEM pair via `WORKSHOP_JWT_PRIVATE_KEY` and
`WORKSHOP_JWT_PUBLIC_KEY` sourced only from the platform secret store or protected
GitHub environment secrets used by the authorized deployment workflow.
Never commit keys or inject them into frontend builds. Keep the same pair across
restarts/redeployments so existing tokens remain valid. Release migration does
not consume JWT keys. Runtime public startup refuses missing keys.

`LLM_API_KEY` and provider keys are optional backend-only secrets. Omitting them
does not block startup or the core Demo; AI requests can report unavailable.
Worker/Redis/vector dependencies are configured separately as the enabled flows
require them. Seed/reset is a separate operator action against the guarded Demo
database, never an API restart hook. `reset-demo --confirm reset-workshop-demo`
forwards to the existing PostgreSQL-only transactional reset guards, including
`DEMO_DATABASE_MARKER`; it is not an HTTP endpoint.

`GET /ready` uses the existing success envelope to report `ready`, `database`,
`demo_mode`, `payment_mode`, `ai_configured`, and `degraded_services`. It returns
200 when the database answers a read-only `SELECT 1`, including when optional
AI configuration is absent (`status=degraded`); database failure returns 503
(`status=not_ready`). It reports configuration, never validates a model key by
making a paid request, and omits keys, provider/DB URLs, passwords and raw errors.
`/health` retains its dependency-free 200 liveness response. The Demo checks
readiness once on load and shows a dismissible notice for AI degradation or
service/API/CORS errors without gating navigation or core actions.

For the public `qwen3.8-flash` configuration, set `LLM_PROVIDER=qwen`,
`LLM_MODEL=qwen3.8-flash`, `LLM_MAX_TOKENS=1200` and `LLM_TIMEOUT_SECONDS=30`
alongside the backend-only key. When both `WORKSHOP_PUBLIC_DEPLOYMENT=true` and
`DEMO_MODE=true`, the chat factory supplies `extra_body={"enable_thinking": false}`
for Qwen to disable its default thinking and avoid extra latency/tokens. Local
full mode, other providers and subscription authentication keep their existing
behavior. See [Qwen thinking configuration](https://www.alibabacloud.com/help/en/model-studio/deep-thinking).

Local Docker Compose needs no new flags: `WORKSHOP_PUBLIC_DEPLOYMENT` defaults to
`false`, preserving migration, location seeding, optional `WORKSHOP_SEED=1` demo
seeding, generated local keys, and local HTTP/same-origin support. Enable public
mode explicitly for cloud deployments; `DEMO_MODE` alone does not enable it.
The Compose worker disables the image's API-only HTTP probe. If deploying the
worker image separately, disable that probe and use the worker platform's process
monitoring instead.

## Vercel Demo build

Use Node 24 and the committed lockfile. Set only public build variables:

```dotenv
EXPO_PUBLIC_PUBLIC_DEPLOYMENT=true
EXPO_PUBLIC_DEMO_MODE=true
EXPO_PUBLIC_API_BASE_URL=https://api.example.com
EXPO_PUBLIC_WS_BASE_URL=wss://api.example.com
```

Public mode requires explicit HTTPS API and WSS WebSocket origins; credentials,
query strings, paths, same-origin markers, and missing endpoints are rejected.
An optional trailing slash is accepted by build preflight and normalized to a
bare origin at runtime, so appended API/WebSocket routes have one separator.
The Vercel build command forces public mode and the `prebuild:web` check fails
before bundling if the public Demo flag or secure endpoints are absent.
Local builds retain their existing localhost/LAN/same-origin behavior. Vercel
exports the Expo Web app to `dist` and rewrites direct SPA navigation to
`index.html`. Do not put payment, database, JWT or AI keys into `EXPO_PUBLIC_*`.

## Vercel Case Study build

```dotenv
VITE_DEMO_URL=https://demo.example.com
VITE_GITHUB_URL=https://github.com/example/workshop-ai-showcase
VITE_SITE_URL=https://case.example.com
```

The existing release-link validation checks these public URLs. Vercel builds
the Vite site to `dist`; direct SPA navigation resolves to `index.html`. No
private credentials belong in `VITE_*` variables.

Configured Demo/video/source actions retain their external destinations. An
unconfigured Demo action links to release status; an unconfigured video action
links to the existing walkthrough with labelled historical screenshots and the
video-in-preparation explanation. No playable recording is implied.

After exporting the Demo with the public build examples above, run
`node --test scripts/service-status-browser.test.cjs` from `frontend/mobile`
for the focused real-browser readiness UI checks. This uses the existing
`showcase/site` Playwright installation and an isolated temporary localhost
server; API responses are intercepted locally. Set
`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` to a local Chromium executable when needed
(the test defaults to macOS Google Chrome). It does not call the live API.

Run `python -m pytest tests/test_deployment_config.py` after installing the
backend requirements and `frontend/mobile` npm dependencies, with Node on PATH,
to exercise all deployment boundaries. Python-only environments skip the client
integration cases explicitly; backend startup/configuration checks still run.

Platform contracts: [Railway config as code](https://docs.railway.com/config-as-code/reference),
[pre-deploy failure behavior](https://docs.railway.com/deployments/pre-deploy-command),
and [Vercel project configuration](https://vercel.com/docs/project-configuration).
