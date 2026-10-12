# Public release record

Updated 2026-10-12. Core release and final deployed Admin isolation checks passed;
the newest CI run did not produce a complete green result. This is not a claim that every
V1 or maintenance item is complete.

## Public destinations and provenance

- [Personal public repository](https://github.com/Grainjin/workshop-ai-showcase)
- [Product introduction](https://jinzhan-ai-coding.vercel.app)
- [Three-role Demo](https://jinzhan-ai-coding-demo.vercel.app)
- [API readiness](https://jinzhan-ai-coding-api.up.railway.app/ready)
- [Approved product introduction PDF](https://jinzhan-ai-coding.vercel.app/documents/Workshop-AI-Product-Introduction-Zhan-Jin.pdf)

The public repository is a sanitized personal showcase snapshot. Source
authorization and attribution remain in README and NOTICE without alteration;
no independent-originality claim is made. The approved PDF SHA-256 is
`7d53ab880799ebc129241bdeeda673f3c334b2eeb62f3c37a58ec84716e734e4`.

## Verified release evidence

API version `718781d` passed the [complete hosted CI run 38194217602](https://github.com/Grainjin/workshop-ai-showcase/actions/runs/38194217602).
Railway deployment `8f11c2b9` reached SUCCESS. The recorded 25 REST/desktop/phone-width
checks passed: synthetic booking 302 ordinary `/ai/chat/sync` returned 200 and an
action draft; cancelling the draft did not execute it; the customer subsequently
confirmed completion explicitly. Existing completed booking 301 was preserved.
Demo payments remain simulated and review context comes from the database; this
does not assert generative-vector retrieval or real funds movement.

The latest operator isolation revision
`b402a48025a2d7dbe1822e9b3318f30b8442fa6e` reached Railway SUCCESS in deployment
`a3100715-04d7-4b30-b609-a6d7ce657c7b` at 2026-10-12 02:31:46 UTC.
Signed-out GET `/ai/oauth` returned early 404 `Not found` at 02:32:37 UTC.
Vercel Demo deployment `4XDqkGq2ryNwan9gJUWsTULAev2Q` is ready/current from
`b402a48`. Final authenticated Admin checks passed on that deployed revision:
desktop 1280×720 at 2026-10-12 02:33:43.150 UTC and phone-width 390×844 at
02:33:46.246 UTC. Both showed the business dashboard without the operator panel,
key, ChatGPT/Grok or save-key controls; each made zero GET `/ai/oauth` requests,
with no overflow or page errors. All task-owned browsers closed.
The acceptance total is 27 PASS: the earlier 25 core checks on `718781d` plus
these two final Admin checks on `b402a48`, not 27 checks rerun on the latest revision.
The [new CI run 38195548801](https://github.com/Grainjin/workshop-ai-showcase/actions/runs/38195548801)
completed with a cancelled backend job and four other jobs passing. It is not
a complete green result: the backend job exceeded its 15-minute limit. Its named
steps, including Test (02:24:08–02:37:46 UTC), reported SUCCESS, but the overall
job was cancelled at 02:37:49 UTC. The earlier full green run on `718781d` does not attest
this newer revision. The key changes have separate focused-test and live
acceptance evidence, rather than an asserted all-green latest CI run.
No credential/status preview is part of public evidence.

## Operations, costs and deferred work

Vercel Hobby and Railway Hobby are active. Infrastructure has a US$8 soft alert
and US$10 hard stop for all resources; model usage has a US$2 stop. The agent
budget is 0. These controls implement the original A$30 target without guaranteeing
the future exchange rate, invoice total or optional-service costs.

The dedicated reset cron runs daily at 17:00 UTC; its first run completed
successfully. Final acceptance objects were preserved; this documentation update
does not invoke a reset.

Recording is deferred by the user, with the visible future entry and honest
not-configured notice retained. A real frontend rollback rehearsal and monthly
maintenance routine remain deferred under the urgent launch decision. Nineteen
upstream dependency alerts remain open; exposure mitigations are not patches and
do not mean those alerts are resolved. Exact model identity/billing, native-mobile
acceptance and complete V1/maintenance completion are not claimed.
