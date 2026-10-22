# AGENTS.md

This is a **config-only repo** — no code, no build, no tests. It holds templates for two config trees; changes ship by copying files out of this repo, never by editing the installed copies.

## What lives here

- `omlx/` — oMLX **server** config templates → `~/.omlx/`
- `opencode/` — OpenCode **client** config + skills → `~/.config/opencode/`
- `.env.example` — the settings the `/omlx-install` skill consumes when
  installing: `OMLX_HOST`, `OMLX_API_KEY`, `OMLX_SECRET_KEY`, `OMLX_BASE_URL`

## Hard rules

- **Never write to `~/.omlx/*` or `~/.config/opencode/*` from a session** except via the `/omlx-install` skill or an explicit user request. Edit the repo copy and install it; the live files run a production server.
- **Never commit secrets.** `omlx/settings.json` ships with sentinels on purpose — leave `REPLACE_ME`, `/Users/YOUR_USER`, and `your-mac.local` intact. `.env` is gitignored; don't add real keys anywhere tracked. A 401/403 against the real server is expected when testing with template values.
- `opencode/opencode.jsonc` is JSONC (comments allowed) but keep it valid JSON; verify edits with a JSONC-tolerant parser, not plain `jq`.

## The model-name contract (things drift silently)

Four places must agree for every model, using the exact server ID form `<Name>-oQ<4|8>-mtp` (e.g. `GLM-5.3-Flash-oQ4-mtp`):

1. `opencode/opencode.jsonc` → `providers.oMLX.models` keys (prefix `oQ/`)
2. `opencode/opencode.jsonc` → `agents.<role>.model`
3. `omlx/model_settings.json` → `models` keys (unsuffixed base entries also exist but are unused; only `-oQ4-mtp`/`-oQ8-mtp` are live)
4. README model table (Model + Quant columns compose the ID)

Adding a model means touching all four. Context limits must also agree: `limit.context` in opencode.jsonc = `max_context_window` in model_settings.json — OpenCode compacts based on its value, so a mismatch either truncates or never compacts.

## Sampling semantics (easy to get wrong)

- `force_sampling` is **off**, so the temperature OpenCode sends wins over the server-side 1.0/0.95/20 defaults. Role temperature comes from the `precise`/`balanced`/`creative` variants in opencode.jsonc, and the turnstile plugin clamps executor/test-runner/debugger ≤ 0.2 and reviewers to 0 at runtime.
- GLM-5.3-Flash deliberately omits `top_k` in model_settings.json — do not "fix" that.
- Only one speculative path per model may be `true` in model_settings.json (oMLX rejects conflicts at load). Currently all four use `mtp_enabled`; a `vlm_mtp_enabled: true` model must have `turboquant_kv_enabled: false`, `guided_grammar_enabled: false`, and no per-model `repetition_penalty`/`presence_penalty` (neutral values 1.0/0.0 are also accepted).

## Server behavior constraints

- Scheduler allows **4 concurrent requests**. Don't fan out more than ~4 parallel subagents at once, or they queue behind each other.
- The server is live and shared (LAN, port 8000). Long benches or bulk loads block agent traffic — run heavy work off-hours or coordinate.
- Throughput benchmarking: use the `/omlx-benchmark` skill (`opencode/skills/omlx-benchmark/`). One bench at a time (server 409s otherwise); batch tests are fixed at pp1024.
- Server binds `0.0.0.0` and is API-key protected — never weaken auth or widen CORS in committed templates beyond the existing placeholders.

## Verification (what "testing" means here)

- `python3 -c "import json; json.load(open('omlx/settings.json'))"` (and same for `omlx/model_settings.json`) — these are pure JSON.
- For `opencode.jsonc`: strip comments first or use a JSONC parser; `python3 -c` with a naive `json.load` is a valid check only while the file contains no comments.
- Grep for leftover `REPLACE_ME` / `YOUR_USER` only in the context of "they should still be there" — their presence in committed files is correct.