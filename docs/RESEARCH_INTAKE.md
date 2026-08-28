# Research Intake

`social-agent research-intake` is a local, scheduled discovery workflow. It
does not draft, approve, or publish content. Codex runs read-only and returns a
strict candidate contract; deterministic local code validates and stores it in
`content/candidates.md`.

The command reads its operator-maintained portfolio from
`content/research-sources.md`. It may use public, non-interactive sources only.
An optional `GITHUB_TOKEN` raises GitHub API limits; no social or publication
credentials are used.

Candidates are capped at ten additions per run and thirty active candidates.
They are deduplicated by normalized URL, expire after thirty days, and remain
in the register as audit records. The most recent summary is written to
`output/research-intake/latest-report.md`.

Review a candidate in `content/candidates.md`, then make the only permitted
handoff to the generation queue:

```bash
uv run social-agent promote-candidate CANDIDATE_ID
```

Promotion validates and deduplicates the URL, then appends only the normalized
URL plus the candidate's angle and audience to `content/urls.md`. The normal
pipeline extracts source evidence again; research notes are not production
evidence.

## Cron

The operator, not the application, installs the schedule. The agreed default
is Tuesday at 07:00 Africa/Casablanca. For a host configured to that timezone,
use an absolute workspace path in the operator's crontab:

```cron
0 7 * * 2 cd /home/naoufel/projects/social-media-agent-python-refactor && /usr/bin/env uv run social-agent research-intake
```

The command uses a local lock to prevent overlapping intake runs. Check the
run report after each execution; a failed Codex invocation exits non-zero and
does not write candidate records.
