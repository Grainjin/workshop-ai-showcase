# Environment matrix

Values describe the intended configuration, not a claim that services are live.
Replace example domains with approved provisioned domains. Database and key values
are provisioned privately; frontend variables are public build inputs.

| Setting | local-full | local-demo | preview | public |
| --- | --- | --- | --- | --- |
| API `WORKSHOP_PUBLIC_DEPLOYMENT` | `false` | `false` | `true` | `true` |
| API `DEMO_MODE` | `false` | `true` | `true` | `true` |
| API `WORKSHOP_PAYMENT_MODE` | `iyzico_sandbox` | `demo` | `demo` | `demo` |
| Web `EXPO_PUBLIC_PUBLIC_DEPLOYMENT` | `false` | `false` | `true` | `true` |
| Web `EXPO_PUBLIC_DEMO_MODE` | `false` | `true` | `true` | `true` |
| PostgreSQL | Local `workshop`, never reset | Dedicated local `workshop_demo` | Dedicated private `workshop_demo_preview` | Dedicated private `workshop_demo_public` |
| Reset marker / seed | Reset refused by Demo flag | `DEMO_DATABASE_MARKER=workshop_demo`, `WORKSHOP_DEMO_SEED=42` | Same marker/seed; scoped preview DB | Same marker/seed; scoped public DB |
| Redis / Celery | Compose `redis:6379`, worker, broker DB 1 / result DB 2 | Same local services when used | Provision private Redis and worker only for enabled flows; otherwise explicit degradation | Same; budget includes provisioned worker and Redis |
| Embeddings / vectors | Compose TEI `http://tei:80/v1`, `Qwen/Qwen3-Embedding-0.6B`, dimension `1024`, local Milvus | Same local optional stack | Optional; no TEI/Milvus infrastructure assumed; vector search can be unavailable | Optional; review fallback remains, readiness reports configured degradation |
| API `WORKSHOP_CORS_ORIGINS` | Approved local HTTP origins in `.env.example` | Same local origins | Exact `https://preview-demo.example.com,https://preview-case.example.com` | Exact `https://demo.example.com,https://case.example.com` |
| Web `EXPO_PUBLIC_API_BASE_URL` | Local HTTP or Compose same-origin | Local HTTP or Compose same-origin | `https://preview-api.example.com` | `https://api.example.com` |
| Web `EXPO_PUBLIC_WS_BASE_URL` | Local `ws://` or derived local API host | Same local value | `wss://preview-api.example.com` | `wss://api.example.com` |
| Uploads | Local `backend/uploads`; private verification storage separate | Local disposable demo storage; no personal files | Disposable synthetic files only; platform filesystem lifecycle documented | Disposable synthetic files only; no durability claim without provisioned storage |
| API JWT pair | Generated local pair | Generated local pair | Stable provisioned RSA pair in platform secret store | Stable provisioned RSA pair in platform secret store |
| Chat | Optional local configured provider / authorized admin auth | Optional local provider | Optional backend-only key, `LLM_PROVIDER=qwen`, `LLM_MODEL=qwen3.8-flash`, `LLM_MAX_TOKENS=1200`, `LLM_TIMEOUT_SECONDS=30` | Same settings; key absent yields AI unavailable while core Demo remains usable |
| Demo AI quotas | Demo quota inactive | `DEMO_AI_DAILY_LIMIT=100`, `DEMO_AI_PER_MINUTE_LIMIT=10` | Same limits; PostgreSQL counters | Same limits; PostgreSQL counters |
| Delivery | Local Compose | Local Compose | Full CI then authorized native Railway/Vercel operation | Full CI plus release checklist and authorized native platform operation |

CORS entries are bare HTTPS origins with no path or trailing slash. API/WS build
inputs require explicit HTTPS/WSS origins; build preflight rejects missing or
insecure endpoints. Rebuild the Expo Web app when changing its Demo flag or URLs.
Set Vite `VITE_DEMO_URL`, `VITE_GITHUB_URL`, and `VITE_SITE_URL` to verified public
destinations before Case Study publication. Never expose API, JWT, payment,
database or embedding credentials in `EXPO_PUBLIC_*` or `VITE_*`.

The preview and public databases must be separate. Do not reference a team or
production database, broaden the reset marker, or make PostgreSQL publicly
reachable for CI. Uploads, Redis and vectors are outside the database reset;
dispose of synthetic artifacts through a separately scoped maintenance operation.
No paid GitHub upgrade is authorized. Total infrastructure plus AI must target at
most A$30/month; enabling optional services requires checking the total first.

The dedicated reset service needs only `WORKSHOP_PUBLIC_DEPLOYMENT=false`,
`DEMO_MODE=true`, `WORKSHOP_PAYMENT_MODE=demo`, its own guarded private
`WORKSHOP_DATABASE_URL`, `DEMO_DATABASE_MARKER=workshop_demo`, and
`WORKSHOP_DEMO_SEED=42`. It has no HTTP surface, JWT pair, LLM key, embedding key,
payment credentials, Redis credentials or inherited workspace-wide secret group.
Its PostgreSQL role must own the application tables/sequences needed for reset;
the API role and migrations role can have separately scoped permissions.
