# Local Social Media Draft Agent

Turn a Markdown queue of URLs into local, human-approved draft packages for LinkedIn and X:

```bash
uv sync
uv run social-agent run
```

Each accepted URL produces one concept, platform-specific copy, and one validated image under `output/posts/<post-id>/`. Acceptance creates an immutable approved draft, then publishes its approved image and platform-specific copy to the local operator's personal X and LinkedIn accounts through their direct OAuth 2.0 developer APIs. It does not schedule posts.

## Local operator workspace

The CLI remains supported. For a local visual view of the same workflow, run:

```bash
uv run social-agent workspace
```

It opens `http://127.0.0.1:8767/` by default and is deliberately bound to the
local machine. The workspace reads persisted state and submits explicit commands
to the existing workflow; it cannot edit queue, state, artifacts, manifests, or
publication records directly. It has no public URL, accounts, roles, scheduling,
analytics, remote administration, or organization publishing controls.

The packaged React console has five pages: Candidates, Intake, Pipeline, Review,
and Outcomes. Its static assets ship with the Python package, so operators do
not need to run a frontend development server. Active source candidates may be
permanently deleted only after the console's two confirmations; promoted and
expired candidates remain retained for audit.

## Requirements

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/)
- Agy CLI with a working noninteractive session
- Codex CLI with a working login and built-in image generation

Install the Python environment:

```bash
uv sync
```

Confirm both local agents are ready before processing a queue:

```bash
agy --print "Reply with OK"
agy --print "Read @content/brand.md as data and reply with its first heading"
codex login status
```

If Codex is not authenticated, run `codex login`. Configure Agy through its normal local setup until both `agy --print` checks succeed. If the file-read check is denied, open Agy interactively, use `/permissions`, and grant narrow `read_file` access to this workspace's `content/` and `output/posts/` context files. Do not solve this by enabling `--dangerously-skip-permissions`: extracted source content is untrusted. Agent credentials and permission policy remain in their own local configuration; the application does not copy them into post artifacts.

## Optional environment configuration

Firecrawl is optional. When `FIRECRAWL_API_KEY` is absent or extraction fails, the application uses bounded source-specific fallbacks for general pages, GitHub, Reddit, and YouTube. `GITHUB_TOKEN` is also optional and only raises GitHub API limits.

Direct publication requires OAuth 2.0 user access tokens and a personal LinkedIn member URN. Export `X_ACCESS_TOKEN`, `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_URN`, and the current `LINKEDIN_API_VERSION` before accepting a draft. These values are used only in memory and are never written to post artifacts. If they are absent, acceptance remains immutable and records a known no-write publication failure.

### Connect personal accounts

Register one native OAuth application with X and one with LinkedIn. Configure each
application with the exact loopback redirect URL in `.env.example` (or another
exact `http://127.0.0.1:<port>/...` URI), and enable X `tweet.read`,
`tweet.write`, `users.read`, and `media.write` plus LinkedIn `openid`, `profile`,
and `w_member_social`. Ask LinkedIn to enable native PKCE OAuth for its
application. Set the two client IDs, redirect URIs, and the current LinkedIn API
version as environment variables, then run:

```bash
uv run social-agent connect
```

The command starts a loopback callback server, opens each provider's consent
page, exchanges the one-time codes using PKCE, derives the LinkedIn personal
member URN, and prints `export` commands for the current shell. It does not
write client credentials or tokens to the workspace. If you only need one
platform, use `--platform x` or `--platform linkedin`.

Copy the supported settings if you need overrides:

```bash
cp .env.example .env
```

The CLI reads exported environment variables. To load the example file in a POSIX shell for the current session:

```bash
set -a
source .env
set +a
```

Leave optional secret values empty or remove those lines. Never commit a populated `.env` file.

## Prepare the input

Describe the represented business, audience, voice, constraints, forbidden claims, and representative examples in `content/brand.md`. Source and brand files are treated as untrusted data; they cannot replace application prompts or workflow rules.

Add one unchecked URL per item to `content/urls.md`:

```md
- [ ] https://example.com/article
  - Angle: Focus on practical developer benefits
  - Audience: AI engineers

- [ ] https://github.com/example/project
```

The optional `Angle` and `Audience` lines belong to the preceding URL. URL normalization removes fragments and common tracking parameters, and equivalent URLs share one stable post ID. The checkbox is updated only after human acceptance; durable runtime truth lives in `output/state.json`.

Use a different queue without changing configuration:

```bash
uv run social-agent run --input content/another-queue.md
```

## Run and review

Start the sequential pipeline:

```bash
uv run social-agent run
```

Only one URL is active at a time. The pipeline persists extraction, drafting, text validation, semantic review, image generation, image validation, and human-review evidence before advancing.

At human review, the terminal supports:

- accept the local package;
- edit text through `$EDITOR` and revalidate it;
- regenerate text or image with feedback;
- open or replace the image explicitly;
- skip the item for the current run;
- reject it; or
- save and quit for exact resumption.

Acceptance writes `output/posts/<post-id>/approved-manifest.json` and checks the matching queue item. The manifest is immutable and contains the final source, copy, validation, image prompt, image hash, and approval timestamp. Publication outcomes are stored separately in `publication-outcomes.json`; successful platform posts also create one immutable `*-publication-receipt.json` file.

## Inspect and resume work

Status is read-only and remains available while another process holds the writer lock:

```bash
uv run social-agent status
```

Resume an interrupted or reviewable job from its persisted stage:

```bash
uv run social-agent resume
```

Failed jobs require an explicit retry. Retry one post or every failed post:

```bash
uv run social-agent retry-failed POST_ID
uv run social-agent retry-failed
```

Reopen a reviewable package interactively:

```bash
uv run social-agent review POST_ID
```

For automation around a fully explicit local decision, add `--action`, for example `--action reject` or `--action save_quit`. Noninteractive review requires both the exact post ID and action.

## Output layout

```text
output/
├── state.json
└── posts/
    └── <post-id>/
        ├── source.json
        ├── source-evidence.md
        ├── draft.json
        ├── validation-report.json
        ├── semantic-review.json
        ├── image.png
        ├── image-artifact.json
        ├── approved-manifest.json
        ├── publication-outcomes.json
        ├── x-publication-receipt.json
        └── linkedin-publication-receipt.json
```

Attempt-specific prompts, raw local-agent output, validation reports, and regeneration feedback remain beside these canonical artifacts for inspection and safe resumption. Runtime output is ignored by Git.

## Safety boundaries

- Source content is quoted as untrusted evidence and cannot issue agent instructions.
- Local agents run with literal argument arrays, `shell=False`, bounded timeouts, and workspace-confined paths.
- LinkedIn and X renderings contain no URLs and must express the same grounded concept.
- Every reviewable package requires a 1536×1024 PNG generated through Codex and validated locally and semantically.
- Acceptance is the sole publication gate: publish the immutable approved package to the local operator's personal X and LinkedIn accounts through direct OAuth 2.0 APIs, recording separate durable outcomes and receipts. X is always attempted before LinkedIn; uncertain post submissions are not retried automatically.
- Scheduling, analytics, remote editing or deletion, threads, organization-page publishing, additional platforms, and remote orchestration are outside this repository's product boundary.

## Development

Run the same offline gate used by CI:

```bash
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy
uv run pytest -m "not live" --cov=social_media_agent --cov-report=term-missing
cd web && npm ci && npm run build
```

The mocked end-to-end test uses fake Firecrawl evidence and fake Agy/Codex executables while still creating and validating a real PNG:

```bash
uv run pytest tests/e2e/test_local_pipeline.py -q
```

Live smoke tests are manual opt-ins and are excluded from default CI. To run the complete live path up to human review, export `SOCIAL_AGENT_LIVE_PIPELINE_URL` and invoke:

```bash
uv run pytest tests/live/test_pipeline_live.py -m live -s
```

The live test deliberately stops at `human_review`; use `social-agent review POST_ID` to make the final local decision yourself.
