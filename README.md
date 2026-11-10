# FrenchFlow public text distribution

This directory is the root of the public repository `kuninao7023-droid/frenchflow-lessons` on branch `main`.
Repository setup started on 2026-11-10. Paid generation is not enabled; the publishing workflow is kept disabled until the owner configures and verifies the dedicated API key and spending controls.
The read-only app endpoint is `https://raw.githubusercontent.com/kuninao7023-droid/frenchflow-lessons/main/feed.json`. No GitHub Pages dependency. Relative pack URLs resolve beside the feed.

Only original learning text belongs here: no MP3/audio, APK, credentials, user history or private source files. Gitignore is a guardrail, not a secret scanner. Never force-add ignored files. Initial feed is empty until a complete month is generated.

## Files and mobile contract

- `catalog/catalog.json`: parent-created base catalog, `{ "schema": 1, "lessons": [...] }`. Do not replace its existing IDs. Must exist and contain validated base lessons before generation; it is intentionally not fabricated here.
- `packs/YYYY-MM.json`: `{ "schema": 1, "month": "YYYY-MM", "lessons": [...] }`, exactly 60 lessons (10 each A1, A2, B1, B2, C1, C2).
- Each lesson has exactly seven nonempty string fields: `id`, `category`, `level`, `french`, `japanese`, `vocabulary`, `grammar`.
- Locally assigned immutable IDs: `monthly-2026-12-a1-001` through `monthly-2026-12-c2-010`. Provider placeholder IDs must be unique within a response, but are never trusted as public IDs.
- `feed.json`: `{ "schema": 1, "packs": [{ "id": "2026-12", "month": "2026-12", "url": "packs/2026-12.json", "sha256": "<64 lowercase hex>", "count": 60 }] }`.
- SHA-256 is over exact UTF-8 file bytes, including final newline. Feed entries are sorted by month. The mobile client must verify hash/count, accept only due months and append immutable IDs; this generator does not replace client validation.

Published packs are append-only: never edit, delete, reuse IDs, or rewrite a pack to correct it. Existing valid month means **zero API calls**, even without credentials; feed is reverified/repaired for complete orphan packs. Changes to any pack already indexed in the feed are rejected. This protects against accidental edits, not an attacker who can edit both pack and feed; Git history/repository access remain the trust boundary.

## Local verification

Python 3.14 standard library; no install step:

```sh
python -m unittest discover -v
```

Tests use explicitly labelled **local synthetic HTTP fixtures**, injected transports and temporary files, not a live OpenAI account. They exercise schema and length floors, duplicate checks against base/history, incomplete/refusal/bad JSON handling, missing configuration/zero budget guards, maximum attempts/calls, stable IDs, atomic replacement cleanup, feed SHA/count verification, publication and idempotency. Passing fixtures do not prove live model support, translation accuracy, CEFR quality or originality.

## Before enabling paid generation

Choose and approve all values; no default paid model, key, budget or prices is supplied:

| Configuration | Where in GitHub | Meaning |
| --- | --- | --- |
| `OPENAI_API_KEY` | Actions secret | Scoped provider project key; never put in Git/files/chat |
| `OPENAI_MODEL` | Actions variable | Model supporting Responses + strict structured outputs |
| `MONTHLY_BUDGET_USD` | Actions variable | Positive finite USD estimate ceiling per invocation |
| `INPUT_PRICE_USD_PER_M` | Actions variable | Positive current uncached input USD per million tokens |
| `OUTPUT_PRICE_USD_PER_M` | Actions variable | Positive current output/reasoning USD per million tokens |

**Set a separate provider-side project budget/alerts/spending controls too.** The local ceiling is an estimate based on your configured prices, not a billing guarantee, not an account-wide or durable calendar-month limit. Failed runs and manual reruns before a successful pack can each incur charges; ephemeral runners do not retain a spending ledger. Review previous provider usage before rerunning and lower the next invocation's approved ceiling accordingly. Provider project budgets may themselves be alert-only; verify actual enforcement with the provider. Exchange rates, taxes, stale prices and provider tokenization/overhead can change actual amounts; no JPY/FX/tax amount is guaranteed.

Each call reserves a conservative input estimate (serialized UTF-8 request bytes + 4096 tokens) plus the full 9000 output-token cap, priced at your configured rates. Reservations are never refunded for failures, missing usage or smaller responses. Before every request the next worst-case estimate must fit the remaining invocation ceiling. At most two attempts per level, six levels, **12 requests total**, timeout 120 seconds per request; HTTP transport has no automatic retry. Usage input/output token counts are validated and reported, not used to loosen reservations. Failed transactions may still be billed. A small budget may stop midway; nothing partial is published. No tools/web/news sources are requested.

With explicitly approved environment values present:

```sh
python tools/generate_monthly.py
# Or an explicitly selected month:
python tools/generate_monthly.py --month 2026-12
```

Default month uses Japan's fixed UTC+09:00. No paid request occurs when required configuration is absent/invalid. Missing base catalog also fails before any request. Errors are deliberately sanitized; provider bodies, Authorization and API keys are never logged. Do not turn on shell tracing or HTTP debug logging around secrets.

## Deployment example (not enabled)

Model documentation checked on 2026-11-08 lists `gpt-6.1-terra` with Responses, strict structured outputs, low reasoning, and standard uncached input/output rates of USD 1/5 per million tokens. Recheck the official model page and the account's actual access/pricing before activation.

A low-volume example uses `OPENAI_MODEL=gpt-6.1-terra`, `MONTHLY_BUDGET_USD=2`, `INPUT_PRICE_USD_PER_M=1`, `OUTPUT_PRICE_USD_PER_M=5`. These are deployment examples, not code defaults or proof that an account is connected. Set the matching dedicated provider project's calendar-month spend control and verify whether hard enforcement is enabled; a notification alone does not stop traffic, and accounting/enforcement can lag. Do not purchase credits or enable automatic top-ups without the owner's approval.

Requests explicitly select low reasoning with a 9000-token output cap. Prompts include up to 50 prior public French passages per level within a 16000-byte text budget to reduce repeats. No private learning or dictionary history is included. Existing seed lessons are structurally validated without imposing the newer generation word floors on legacy material.

Official model reference: `https://developers.openai.com/api/docs/models/gpt-6.1-terra`

## Generation/publication behavior and limits

Responses endpoint: `https://api.openai.com/v1/responses`, `store: false`, strict `text.format` JSON schema. Parse raw `output[]` message `content[]` `output_text`, never the SDK-only convenience accessor. Require completed responses; reject refusal/incomplete/bad JSON, wrong count/levels and exact duplicate French text/IDs against the entire base plus all published packs before publication. A retry asks for fresh samples; it does not publish the failed sample.

Prompt requests original fictional everyday/reflection lessons, full Japanese translations, vocabulary and grammar explanations, not news claims or quoted real works. Word-count floors (French whitespace-separated words) are A1 3, A2 5, B1 12, B2 25, C1 45, C2 60; target ranges are substantially higher. These are approximate heuristics, not language detection, semantic duplicate/plagiarism detection or pedagogical certification. Nonempty Japanese/vocabulary/grammar strings are checked, not their linguistic correctness. Human quality review is still advisable; content is not proven original merely by passing exact-match checks.

All six levels must validate before any public file write. JSON uses same-directory temporary files, flush/fsync and `os.replace`. Pack is atomically replaced first, read back and verified, then feed is atomically replaced. This is per-file atomicity, not a two-file filesystem transaction: an interrupted run can leave a complete unindexed pack; rerun verifies and indexes it without paid generation. Failed/partial packs are never written. Run only one local publisher at a time; workflow concurrency serializes GitHub runs. Concurrent manual filesystem edits are outside this guarantee.

## GitHub Actions

Workflow `.github/workflows/monthly.yml` is intended at the public repository root. Cron `0 0 1 * *` is UTC midnight / 09:00 Japan on the first day, plus `workflow_dispatch`; hosted scheduling can be delayed and repository scheduling policies apply. Dispatch always targets current Japan month on `main`. Global workflow concurrency has `cancel-in-progress: false`; only `contents: write` permission is requested. Tests run before the secret-bearing generation step. The final step stages/commits only `packs/*.json` and `feed.json` and pushes only if changed. Nothing commits environment variables or runtime logs. Branch rules must permit this bot push; conflicting manual changes fail rather than force-push. Repository ownership/OAuth/creation/configuration remain separate tasks.

Official action tag/commit references were read from GitHub's public API during setup (chosen versions, not a claim of latest):

- `actions/checkout` v6.0.0: `1af3b93b6815bc44a9784bd300feb67ff0d1eeb3`
- `actions/setup-python` v6.0.0: `e797f83bcb11b83ae66e0230d6156d7c80228e7c`

Primary references for re-verification:

- `https://api.github.com/repos/actions/checkout/git/ref/tags/v6.0.0`
- `https://api.github.com/repos/actions/setup-python/git/ref/tags/v6.0.0`
- `https://github.com/actions/checkout/releases/tag/v6.0.0`
- `https://github.com/actions/setup-python/releases/tag/v6.0.0`
- `https://developers.openai.com/api/reference/resources/responses/methods/create`
- `https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses`

Live OpenAI behavior and actual hosted GitHub execution remain unverified until the owner selects configuration and authorizes deployment. This setup makes no live API success claim.
