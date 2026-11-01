# Settings → AI: BYO provider keys and model selection (issue #13) — shared contract

Backend and frontend are built in parallel against this contract. Neither side
changes it unilaterally; raise a question to the coordinator instead.

Scope guardrail: this is the **configuration foundation only**. No report
generation, enrichment, RAG, agents, per-user accounts, custom base URLs/proxies,
or usage budgets. Configuration alone must never send indicators, reports, or any
other instance data to a provider.

## Providers

Fixed set (string enum `AiProvider`): `anthropic`, `openai`, `openrouter`, `xai`.
Display names: Anthropic, OpenAI, OpenRouter, xAI (Grok). Base URLs are hard-coded
in the adapters; there is no base-URL field anywhere.

## Permissions

Every endpoint below uses the existing `require_admin` dependency (admins and API
keys, same as API-key and member management). Non-admin users get 403 on all of
them, including reads. The frontend tab is `adminOnly: true`.

## Data model (migration `006`)

Use `sa.JSON` (not JSONB) so the SQLite test suite works.

`ai_providers`
| column | type | notes |
|---|---|---|
| provider | varchar(32) pk | `AiProvider` value (CHECK constraint) |
| credentials_encrypted | bytea not null | `encrypt_config({"api_key": ...})` from `cti.core.security` |
| key_hint | varchar(8) null | last 4 chars of the key; null when the key is shorter than 12 chars |
| model_cache | json null | last successful discovery result: list of `AiModel` dicts |
| models_fetched_at | timestamp null | when `model_cache` was written |
| last_check_status | varchar(16) null | `ok` \| `error` |
| last_check_category | varchar(32) null | `AiErrorCategory` when status is `error` |
| last_checked_at | timestamp null | |
| created_at / updated_at | timestamp | TimestampMixin |

`ai_settings` (single row, `id = 1`, CHECK `id = 1`)
| column | type | notes |
|---|---|---|
| id | int pk | always 1 |
| default_provider | varchar(32) null fk ai_providers.provider ON DELETE SET NULL | |
| default_model | varchar(255) null | exact ID as entered, never normalised |
| default_model_is_custom | bool not null default false | |
| updated_at | timestamp | |

Invariants:
- `default_provider` and `default_model` are both null or both set. Deleting a
  provider clears **both** default fields in the service layer as well as through the FK.
  That leaves an explicit unconfigured state with no fallback to another provider.
- Replacing a key (PUT) clears `model_cache`, `models_fetched_at`, and the
  `last_check_*` fields. It keeps the default selection.

## Error categories (`AiErrorCategory`)

`invalid_credentials` (401), `permission_denied` (403), `rate_limited` (429),
`insufficient_quota` (402, or a provider body that says quota/billing),
`model_unavailable` (404 on a model, or an unknown model ID), `timeout`,
`network_error`, `provider_error` (5xx or unparseable), `not_configured`.

Error payload shape: `{ "category": AiErrorCategory, "message": str }`. `message` is
a fixed, human-readable string per category, optionally followed by the provider
HTTP status. It **never** echoes the API key, request headers, request bodies, or
raw provider response bodies.

## Types (JSON)

```ts
type AiProvider = 'anthropic' | 'openai' | 'openrouter' | 'xai'
type ModelSource = 'live' | 'cache' | 'fallback'

interface AiModel {
  id: string            // exact provider model ID
  name: string          // friendly name; equals id when the provider gives none
  context_length?: number | null
}

interface AiError { category: AiErrorCategory; message: string }

interface AiProviderStatus {
  provider: AiProvider
  display_name: string
  configured: boolean
  key_hint: string | null          // e.g. "a1b2"; UI renders "••••a1b2"
  models_fetched_at: string | null // ISO
  last_check_status: 'ok' | 'error' | null
  last_check_category: AiErrorCategory | null
  last_checked_at: string | null
  setup_url: string                // provider console URL for creating a key
}

interface AiDefault { provider: AiProvider; model: string; is_custom: boolean }

interface AiSettings {
  providers: AiProviderStatus[]    // always all four, configured or not, fixed order above
  default: AiDefault | null
}

interface AiModelList {
  provider: AiProvider
  source: ModelSource              // live = fetched now, cache = stored last-good, fallback = built-in catalog
  fetched_at: string | null
  models: AiModel[]
  error: AiError | null            // set when a live fetch was attempted and failed
}

interface AiCheckResult { ok: boolean; error: AiError | null; checked_at: string }

interface AiInferenceResult { ok: boolean; error: AiError | null; latency_ms: number | null }
```

No response type ever has an `api_key` field.

## Endpoints (prefix `/api/v1/settings/ai`)

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `` | — | `AiSettings` |
| PUT | `/providers/{provider}` | `{ "api_key": str }` (1–512 chars after strip; stored stripped) | `AiProviderStatus`. Creates or replaces the key. **No network call.** |
| DELETE | `/providers/{provider}` | — | 204. 404 if not configured. Clears the default if it pointed here. |
| POST | `/providers/{provider}/check` | — | `AiCheckResult`. Non-billable credential/connection check (see adapters). Persists `last_check_*`. 409 `not_configured` if no key. |
| GET | `/providers/{provider}/models?refresh=false` | — | `AiModelList` (see discovery rules) |
| POST | `/providers/{provider}/inference-test` | `{ "model": str, "confirm": true }` | `AiInferenceResult`. 422 unless `confirm` is literally `true`. |
| PUT | `/default` | `{ "provider", "model", "is_custom": bool }` | `AiDefault` |
| DELETE | `/default` | — | 204 (idempotent) |

Unknown `{provider}` path value → 422 (enum validation). Provider-side failures
are returned **inside** the 200 body (`error` / `ok: false`), not as 5xx.

### Discovery rules (`GET /models`)

1. Not configured → 409 `{category: not_configured}`.
2. `refresh=false`, and `model_cache` exists and is younger than 1 hour → `source: cache`, no network.
3. Otherwise fetch live (httpx, 10 s total timeout). On success, write `model_cache` and
   `models_fetched_at` and return `source: live`.
4. When a live fetch fails, return the existing `model_cache` (`source: cache`) if there is one,
   else the built-in fallback catalog (`source: fallback`), with `error` set.
   Failure never deletes the cache or the default selection.
5. Models are sorted by `name`. Results are filtered to text-generation models where
   the provider exposes capabilities (OpenRouter `architecture.output_modalities`
   includes `text`), or by a documented ID heuristic (OpenAI: drop `embedding`,
   `tts`, `whisper`, `dall-e`, `moderation`, `transcribe`, `realtime`, `image`, `audio`,
   `search`). The filter is best-effort; the custom-ID path covers anything it hides.

### Default validation (`PUT /default`)

- Provider must be configured → else 409 `not_configured`.
- `model`: reject empty, whitespace-only, > 255 chars, or containing control
  characters (422). Otherwise store **byte-for-byte as sent**, with no trim and no case change.
- `is_custom=false`: the model must appear in the provider's `model_cache`, or in the
  fallback catalog when no cache exists, else 422 telling the user to choose a listed
  model or use a custom ID. Validation uses stored data only and **never** makes a
  live call.
- `is_custom=true`: the format checks above are the only checks.

### Inference test

Explicitly billable, and only on explicit confirmation. It sends one fixed prompt
(`"Reply with the single word: OK"`, max output tokens ≤ 16) to the chosen model. It
never sends instance data. It does not change the default or the cache.

## Adapters (`src/cti/services/ai/`)

Shared interface in `base.py`, one module per provider, and `registry.py` to map
`AiProvider` → adapter. Every call is async httpx with a 10 s timeout; HTTP status
maps to `AiErrorCategory` in one shared helper.

| Provider | List models (also the non-billable check) | Inference test |
|---|---|---|
| anthropic | `GET https://api.anthropic.com/v1/models?limit=1000` headers `x-api-key`, `anthropic-version: 2023-06-01`; name = `display_name` | `POST /v1/messages` |
| openai | `GET https://api.openai.com/v1/models` Bearer; name = id; ID-heuristic filter | `POST /v1/chat/completions` |
| openrouter | list: `GET https://openrouter.ai/api/v1/models` (Bearer sent). Check: `GET https://openrouter.ai/api/v1/key`, because the model list is public and proves nothing about the key; name = `name`, `context_length` | `POST /api/v1/chat/completions` |
| xai | `GET https://api.x.ai/v1/models` Bearer; name = id | `POST /v1/chat/completions` |

`catalog.py` holds a small fallback list per provider (a few current text models
each), with a comment saying it is a manually maintained convenience that may go
stale. The UI labels it "Built-in list (may be out of date)".

## Secrets handling

- Keys are written only through `encrypt_config`; the plaintext exists only inside the
  request handler and the adapter call.
- Never log keys, the `Authorization` / `x-api-key` headers, or request or response
  bodies. Do not let httpx exceptions (which can carry request objects) reach log
  messages or responses verbatim.
- Tests use obvious fake keys such as `sk-test-not-a-real-key-0000`. A test asserts
  that the raw key appears in no response body from any endpoint.
- Frontend: the key input is `type="password"` with `autoComplete="off"`. It is
  cleared after a successful save and never put in localStorage, sessionStorage,
  the URL, query-cache keys, or toasts.

## Frontend

- `types/ai.ts`, `api/ai.ts`, `hooks/useAiSettings.ts` (TanStack Query; invalidate
  `ai-settings` and that provider's models query after key PUT/DELETE).
- `components/settings/AiSettings.tsx`: an intro panel stating that providers are
  external services with their own charges and data-handling policies, and that
  nothing is sent until a future feature asks. Then one card per provider:
  configured badge, masked hint, set/replace/remove key (remove asks for
  confirmation), "Check connection" (described as free, no inference), and
  "Refresh models". Then a Default model section.
- `components/settings/ModelPicker.tsx`: searchable combobox that filters on name and
  ID, shows the friendly name with the exact ID in monospace, and has a source label
  (Live / Cached <time> / Built-in list (may be out of date)). It includes an explicit
  "Use custom model ID…" option that switches to a text input which preserves exact
  input. Discovery errors show inline and never clear the current selection or block
  custom entry.
- Inference test: a separate button that opens a confirm dialog stating it sends one
  tiny fixed prompt and may incur provider charges. Only the confirm action sends
  `confirm: true`.
- SettingsPage: add tab `{ id: 'ai', label: 'AI', adminOnly: true }`.

## Docs

The README gains an "AI providers" section covering supported providers, where to
create keys, that `FEED_ENCRYPTION_KEY` also encrypts AI keys (back it up; rotating it
makes stored keys unreadable, so re-enter them), that usage costs and data policies
belong to the provider, and that only the confirmed inference test makes a billable
call.
