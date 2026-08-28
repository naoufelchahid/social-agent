# Operator Workflow

This guide explains how one local operator turns a queued URL into an approved
post for personal X and LinkedIn accounts. The application is local-first: it
stores source evidence, drafts, validation results, generated images, approvals,
and publication outcomes in this workspace. It does not schedule posts, publish
to organization pages, or allow remote edits or deletion.

## 1. One-time setup

Install the locked Python environment and confirm the command is available:

```bash
uv sync
uv run social-agent --help
```

The drafting workflow also needs authenticated local Agy and Codex CLIs. Check
them before placing work in the queue:

```bash
agy --print "Reply with OK"
codex login status
```

Create a local configuration file if it does not already exist:

```bash
cp .env.example .env
```

`.env` is ignored by Git. Keep tokens and client secrets there or in your shell;
never add them to `.env.example`, documentation, commits, or generated artifacts.

Load the file for the current POSIX-shell session before running commands that
need configuration:

```bash
set -a
source .env
set +a
```

The CLI reads environment variables; it does not load `.env` automatically.

## 2. Configure publication accounts

Publication is optional. Without all four values below, local approval still
works, but the workflow records a no-write publication failure.

```bash
X_ACCESS_TOKEN=
LINKEDIN_ACCESS_TOKEN=
LINKEDIN_AUTHOR_URN=
LINKEDIN_API_VERSION=<current-YYYYMM-version>
```

`LINKEDIN_API_VERSION` is the current `YYYYMM` release value required by
LinkedIn's versioned REST APIs. For example, the August 2026 release is
`202608`. Check LinkedIn's current Posts API documentation when onboarding or
updating the integration; do not leave it blank.

The account connection command obtains new session-only values through OAuth
2.0 authorization-code flow with PKCE. Before using it, register these exact
loopback callbacks with the providers:

```bash
X_REDIRECT_URI=http://127.0.0.1:8765/x/callback
LINKEDIN_REDIRECT_URI=http://127.0.0.1:8766/linkedin/callback
```

Set the corresponding client IDs in `.env`. Enable X `tweet.read`,
`tweet.write`, `users.read`, and `media.write`; enable LinkedIn `openid`,
`profile`, and `w_member_social`, and ask LinkedIn to enable native PKCE for the
application.

Then load `.env` and connect the accounts:

```bash
uv run social-agent connect
uv run social-agent connect --platform x
uv run social-agent connect --platform linkedin
```

The command opens the provider consent page and waits for the configured local
callback. On success it prints shell `export` commands. Run those commands in
the same terminal session; the application never saves OAuth tokens itself.

## 3. Prepare the queue and brand context

Describe the business, audience, voice, prohibited claims, and examples in
`content/brand.md`. Add unchecked URLs to `content/urls.md`:

```md
- [ ] https://example.com/article
  - Angle: Focus on practical developer benefits
  - Audience: AI engineers
```

`Angle` and `Audience` are optional and belong to the preceding URL. The source
content and queue metadata are treated as data, not instructions. One URL
creates one content concept, one LinkedIn rendering, one X rendering, and one
shared validated PNG image.

## 4. Run, inspect, and approve

You may use the local browser workspace instead of assembling status and review
information from terminal commands:

```bash
uv run social-agent workspace
```

It binds only to `http://127.0.0.1:8767/`. The workspace shows pipeline state,
candidate portfolio, research reports, review packages and publication outcomes;
it submits the same explicit local workflow operations as the CLI. It never
shows OAuth tokens or secrets. Before browser acceptance, it states exactly that
the action creates an immutable approved draft and immediately starts X then
LinkedIn publication to the operator's personal accounts.

Start the sequential local workflow:

```bash
uv run social-agent run
```

Use another queue without changing the saved configuration:

```bash
uv run social-agent run --input content/another-queue.md
```

For each URL, the application persists source extraction, draft attempts,
deterministic text validation, independent semantic review, image generation,
image validation, and the terminal review package under
`output/posts/<post-id>/`.

At the terminal review prompt, choose one action:

| Key | Action | Result |
| --- | --- | --- |
| `a` | Accept | Creates the immutable approval and attempts publication. |
| `e` | Edit | Opens `$EDITOR`, then revalidates the draft. |
| `t` | Regenerate text | Requests feedback, then returns to text validation. |
| `i` | Regenerate image | Requests feedback, then regenerates and validates the image. |
| `o` | Open image | Opens the local image only when explicitly requested. |
| `p` | Replace image | Copies and validates a supplied 1536×1024 PNG. |
| `s` | Skip | Leaves the item pending for later. |
| `r` | Reject | Marks the item rejected; it will not publish. |
| `q` | Save and quit | Records the current stage for exact resumption. |

Acceptance is the only normal publication boundary. It first writes
`approved-manifest.json`, an immutable snapshot of the final source, text,
validation, image hash, and approval time. It then tries both personal platforms
independently using the exact approved text and image. A failed X attempt does
not prevent the LinkedIn attempt, and vice versa. A successful receipt and all
safe outcome details are stored separately from the approval manifest.

Never use approval to test unreviewed or changed copy: edit or regenerate it,
review it again, and then accept the resulting immutable package.

## 5. Publish a reviewed package

There is intentionally no standalone `publish` command. The publish command is
the explicit `accept` action at human review: this prevents unpublished text or
an unreviewed image from being sent to either provider.

Use this sequence to publish a newly reviewed queue item:

```bash
# 1. Load the current OAuth values into this terminal.
set -a
source .env
set +a

# 2. Start the pipeline and wait for its human-review screen.
uv run social-agent run

# 3. At the displayed prompt, type a and press Enter.
# Action [a/e/t/i/o/p/s/r/q] (...): a
```

For a package that is already at the `human_review` stage, resume its review
instead:

```bash
uv run social-agent status
uv run social-agent review POST_ID

# At the review prompt:
# Action [a/e/t/i/o/p/s/r/q] (...): a
```

`a` atomically creates the immutable approval manifest first, then attempts X
and LinkedIn. Do not use `a` for a package that is already approved: the manifest
is intentionally immutable, so it cannot be accepted or published a second time
through the normal workflow.

After the command returns, inspect the recorded provider results:

```bash
uv run social-agent status
find output/posts/POST_ID -maxdepth 1 -name '*publication*' -print
```

An X failure—for example, due to account quota—does not cancel the LinkedIn
attempt. A result file records `published`, `failed`, or `unknown` for each
platform; `unknown` means the provider may have accepted the request, so do not
blindly retry it.

## 6. Check progress and recover safely

Inspect state without changing it:

```bash
uv run social-agent status
```

Resume an interrupted or reviewable job at its saved stage:

```bash
uv run social-agent resume
```

Retry failed pipeline work explicitly. Use a post ID for one job, or omit it for
every failed job:

```bash
uv run social-agent retry-failed POST_ID
uv run social-agent retry-failed
```

Reopen a job currently waiting for human review:

```bash
uv run social-agent review POST_ID
```

For an explicit local noninteractive decision, specify both the post ID and an
action, for example:

```bash
uv run social-agent review POST_ID --action reject
uv run social-agent review POST_ID --action save_quit
```

Use `status` to obtain the post ID and current stage. The writer lock permits
only one mutating workflow at a time; `status` remains safe to run while another
workflow is active.

## 7. Inspect results

The durable state is `output/state.json`. Each post has a directory under
`output/posts/<post-id>/`, commonly containing:

- `source.json` and `source-evidence.md`: extraction provenance and quoted source
  evidence;
- `draft.json`, validation reports, and semantic-review results;
- `image.png` and `image-artifact.json`: the final image and its integrity data;
- `approved-manifest.json`: the immutable locally accepted package;
- `publication-outcomes.json`: safe per-platform publication results; and
- `x-publication-receipt.json` or `linkedin-publication-receipt.json`: remote
  identifiers for successful posts.

Do not edit approved manifests, receipts, or publication outcome files. They are
evidence of what the local operator approved and what the providers reported.
