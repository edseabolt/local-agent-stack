# AGENTS.md

This is a **config-plus-tooling repo** — no build; Python tooling (chart
generation, benchmark and install scripts) ships with stdlib `unittest`
tests, run directly with `python3 -m unittest`. It holds templates for two
config trees; changes ship by copying files out of this repo, never by
editing the installed copies.

## Writing & documentation (standing instruction, Nov 2026)

All prose written in this repo must follow ISO 24495-1 (Plain language —
Part 1: Governing principles and guidelines). This applies everywhere prose
is written: documentation (README, comments in JSONC config), commit
messages, and agent/skill definition text. Prioritize the standard's core
principles: write for your readers, keep it findable and usable, and say
only what's needed — nothing more.

Prose in committed files must be self-contained: a reader without this
session's context must still understand it. Never reference chunks,
acceptance criteria, plan files, or issue numbers in docs, config comments,
or skill text — those citations belong in the plan file and the commit
message.

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

Four places must agree for every model, using the exact server ID form `<Name>-oQ<4|6|8>-mtp` (e.g. `GLM-5.3-Flash-oQ6-mtp`):

1. `opencode/opencode.jsonc` → `providers.oMLX.models` keys (prefix `oQ/`)
2. `opencode/opencode.jsonc` → `agents.<role>.model`
3. `omlx/model_settings.json` → `models` keys (unsuffixed base entries also exist but are unused; only the `-oQ4-mtp`/`-oQ6-mtp`/`-oQ8-mtp` entries are live)
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

## Python coding practices (standing instruction, Nov 2026)

These rules apply to every Python file in the repo (skill scripts under
`opencode/skills/*/scripts/`, and any future Python code). They are enforced
on every change, not aspirational — a review that spots a violation rejects
the change or refactors it in the same change set.

- **Full typing** — every function is fully annotated: parameters, return
  values, and module-level constants where the type is not obvious. Use
  `typing`/builtin generics (`list[str]`, `dict[str, str]`, `Path | None`).
  `mypy --strict` (or an equivalent checker) should pass with no
  `--ignore-missing-imports` surprises beyond stdlib-only third-party gaps.
- **Function size cap** — a function is at most 20–30 lines (20 is the
  target, 30 is the hard ceiling before a refactor is mandatory). Break
  functions down by the concerns inside them; a function that needs a
  comment to explain its structure is already too big. `main()` orchestrates
  only — parse args, call steps, print.
- **DRY** — the same decision, rule, constant, or transformation lives in
  exactly one place. Values derived in one function are passed in, not
  recomputed at each call site. Logic shared between two scripts moves into
  a small shared module next to them, not copy-pasted.
- **SOLID / single responsibility** — one concern per function and per
  module; dependencies flow one way; no import cycles.
- **Security** — never store secrets in code; validate all external input
  (CLI args, JSON payloads, env values); keep secrets out of logs and error
  messages; keep generated secret files `0600`.
- **Performance awareness** — write efficient code by default; profile
  before optimizing; avoid premature optimization but mind algorithmic
  complexity.
- **Testing** — tests for critical paths and complex logic, with descriptive
  names that explain the expected behavior. Prefer test frameworks that
  report per-test results (e.g. `pytest` or `unittest`) over bare
  module-level `assert` scripts, so a failure names the case that failed.
  Tests carry docstrings too.
- **Error handling** — handle errors explicitly with meaningful messages;
  never swallow an exception silently unless the failure is genuinely
  best-effort (and say so in a comment); do not expose secrets in messages.
- **Docstrings & comments** — every function and module carries a docstring
  (Google style) that says what it is for; comments explain "why", not
  "what". Docstrings and comments are self-contained: no references to
  chunks, acceptance criteria, plan files, or issue numbers.
- **Naming** — descriptive, self-documenting names; `snake_case` for
  functions, variables, and modules; `CapWords` for classes;
  `UPPER_SNAKE` for module-level constants.
- **Formatting** — PEP 8 layout, consistent indentation and spacing
  (a formatter such as `black` or `ruff format` is the mechanical baseline).
- **Dependencies** — stdlib first. Only add a third-party dependency when
  the stdlib genuinely cannot do the job; scripts here are expected to run
  on a bare macOS `python3`.

## Verification (what "testing" means here)

- `python3 -c "import json; json.load(open('omlx/settings.json'))"` (and same for `omlx/model_settings.json`) — these are pure JSON.
- For `opencode.jsonc`: strip comments first or use a JSONC parser; `python3 -c` with a naive `json.load` is a valid check only while the file contains no comments.
- Grep for leftover `REPLACE_ME` / `YOUR_USER` only in the context of "they should still be there" — their presence in committed files is correct.