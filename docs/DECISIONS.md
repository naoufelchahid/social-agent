# Architectural Decisions

This file is append-oriented. Record durable choices, replacements, and intentional removals; use Git history for routine edits.

## 2026-08-25 — D001: Local sequential Python pipeline

Replace LangGraph orchestration with a plain Python 3.11+ state machine and Typer CLI. The product processes one Markdown URL at a time and persists after every stage. Remote graph servers, threads, Agent Inbox, and LangSmith are not part of the replacement.

## 2026-08-25 — D002: One concept, two platform renderings

Each URL produces one content concept rendered separately for LinkedIn and X so formatting and length respect each platform. Neither rendering contains source links. Both share one generated image.

## 2026-08-25 — D003: Separate local writer and reviewer

Agy is the writer and is invoked as `agy --print <prompt>`. Codex is an independent reviewer invoked noninteractively with a JSON schema. Agent processes use `shell=False`, explicit timeouts, fresh sessions, and persisted file-based context.

## 2026-08-25 — D004: Firecrawl first with local fallbacks

Firecrawl is attempted first when configured. General pages, GitHub, Reddit, and YouTube each have deterministic fallbacks, allowing the workflow to continue when Firecrawl is unavailable. Source material is untrusted evidence and cannot supply workflow instructions.

## 2026-08-25 — D005: Mandatory Codex-generated image

Every human-reviewable post must include one image generated through Codex `$imagegen`. The final asset must be copied into the post artifact directory and validated locally. Image generation or validation exhaustion fails the job; there is no text-only success path.

## 2026-08-25 — D006: Human approval is the product boundary

The terminal human node supports acceptance, editing, regeneration, skipping, rejection, and safe quit/resume. Acceptance creates a local immutable manifest. Publication, scheduling, social authentication, and analytics are separate future scope.

## 2026-08-25 — D007: File-backed resumability and governed memory

Runtime progress is stored atomically in `output/state.json`; per-post artifacts make stages independently resumable. `AGENTS.md` points every new session to the stable plan, mutable project status, and append-oriented decisions. Conversation memory is never the source of truth.

## 2026-08-25 — D008: Versioned local-agent JSON contracts

Agy draft output and Codex semantic review output are independently validated against strict schema-version-1 Pydantic contracts. Prompts reference persisted workspace files instead of embedding source or brand bodies; prompt templates, output schemas, raw local output, and validated results remain under the post artifact directory. Malformed Agy output receives one formatting-only repair call, while malformed Codex review output fails closed.

## 2026-08-25 — D009: Text edits preserve the reviewed image brief

The terminal text editor may change the concept and platform renderings but cannot change the image brief, because doing so would silently detach the already reviewed image from its approved intent. A reviewer changes visual direction through Regenerate image with feedback or Replace image, both of which require fresh local and semantic image validation.

## 2026-08-26 — D010: Legacy hosted workflow is permanently replaced by the local CLI

The local Python state-machine CLI is the sole product implementation. TypeScript, Node, LangGraph/LangSmith, Supabase, hosted-model SDK inference, Arcade, Slack, scheduling, publishing, cron, curation, repurposing, reflection, and image discovery were intentionally removed rather than retained as dormant alternatives.

Their replacement is the sequential local workflow: Markdown queue → bounded extraction with local fallbacks → Agy draft → deterministic and independent Codex review → mandatory local Codex image → terminal human approval → immutable local manifest. Reintroducing any removed capability requires an explicit scope decision, updated safety boundaries, tests, and a new acceptance gate.

## 2026-08-27 — D011: Human approval triggers image-complete X and LinkedIn publication

The local CLI is extended for a single local operator: accepting an immutable
approved draft immediately publishes its platform-specific copy and approved
image to personal X and LinkedIn accounts. It calls Arcade through the direct
Python SDK; X publishes first, followed by a private custom Arcade tool for the
LinkedIn image-post flow. Approval remains immutable and separate from each
platform's durable publication outcome and receipt. Only proven no-write
failures retry automatically; an outcome that is uncertain after submission
requires explicit operator resolution to prevent duplication.

Arcade Cloud manages OAuth after a separate local `connect` command using one
stable locally stored operator ID. Scheduling, analytics, remote editing or
deletion, threads, organization-page publishing, and additional platforms are
explicitly out of scope.

## 2026-08-27 — D012: Publication is an active product boundary

D011 supersedes the publication exclusions in D006 and D010. The active
product boundary permits only immediate, acceptance-triggered,
image-complete publication to the local operator's personal X and LinkedIn
accounts via Arcade. Approval is immutable; platform outcomes and receipts are
durable and separate. The excluded capabilities in D011 remain out of scope.

## 2026-08-27 — D013: Direct OAuth 2.0 replaces Arcade for publication

Direct X and LinkedIn OAuth 2.0 developer APIs replace Arcade Cloud and its
private publishing server. The local operator supplies OAuth access tokens, a
LinkedIn personal-member URN, and a current LinkedIn API version through local
secret configuration. X uploads and creates its post before LinkedIn starts its
image upload. Any post request whose result is uncertain records `unknown` and
is never retried automatically.

## 2026-08-27 — D014: Scheduled research intake remains outside the publishing pipeline

An opt-in local Codex research intake may run on a cron schedule to discover
source candidates. It writes candidates to a separate local list, never to the
runnable URL queue, and it cannot draft, approve, or publish. The local
operator deliberately promotes a candidate before the existing human-approved
draft workflow may use it. This narrowly reintroduces scheduled curation while
preserving the approval and publication boundaries.

## 2026-08-27 — D015: Research intake uses a bounded, operator-mediated portfolio

The intake runs weekly and retains at most ten new source candidates per run
and thirty candidates in total. Its fixed, vetted capability allowlist may
research only public GitHub repositories, public Reddit discussions, and
operator-approved professional publications. Candidates enter a separate local
list; an explicit CLI promotion validates and deduplicates one candidate before
appending it to `content/urls.md`. This keeps external material untrusted and
the production queue operator-controlled.

## 2026-08-27 — D016: Candidate records are auditable and time-bounded

`content/candidates.md` is the human-readable local candidate register. Each
record carries the canonical URL, provenance and dates, grounded evidence,
proposed Eudaimonia angle, concrete French SME/ETI use case, intended audience,
and a scored rationale. The score evaluates editorial-pillar fit, business
relevance, evidence quality, novelty, recency, and safety/reputation risk;
unsupported, promotional, off-topic, or non-translatable sources are rejected.
The operator installs the documented Tuesday 07:00 Africa/Casablanca cron entry;
the application never edits their crontab and uses a lock to prevent overlap.
Unpromoted candidates expire after thirty days and remain as `expired` audit
records rather than being deleted.

## 2026-08-27 — D017: Intake has constrained roles and observable partial failure

`content/research-sources.md` is the versioned allowlist of GitHub API search
queries, public Reddit communities, and professional publication/RSS feeds;
the GitHub Trending webpage is not scraped. A constrained collector retrieves
public evidence, a research evaluator returns structured selection findings,
and deterministic local code alone validates and writes the candidate register.
On a source-family failure, the run continues only with valid findings and
writes an intake run report identifying the skipped family and stable reason;
it never writes malformed or partial candidate records.

## 2026-08-28 — D018: Intake has no interactive authority or production evidence shortcut

Discovery uses only public, non-interactive interfaces: GitHub API search,
public Reddit retrieval, and allowed publication feeds or pages. An optional
`GITHUB_TOKEN` only raises API limits; no browser, social, or publication
credential is available to intake. Promotion appends only the normalized URL
and operator-approved angle and audience, so the existing production pipeline
performs fresh extraction. Initial selection is limited to AI-use-case
prioritisation, workflow adoption, governance/risk, and contextualised AI;
tool-release news, model leaderboards, funding news, and purely technical
material require a clear executive-decision or business-workflow translation.

## 2026-08-28 — D019: Initial portfolio and intake bounds are deliberately narrow

The initial GitHub queries cover `llm`, `ai-agents`, `workflow-automation`, and
`artificial-intelligence` with activity and adoption filters. Reddit research is
limited to `r/ArtificialInteligence`, `r/MachineLearning`, `r/LocalLLaMA`, and
`r/AI_Agents`; official CNIL, Bpifrance Le Lab, Hub France IA, OECD AI, and NIST
AI feeds or pages supply professional publications. Each configured source
discovers at most twenty URLs; retrieval lasts at most fifteen seconds and
retains at most 100 KB of evidence per URL. A run never retries within itself
and stops after fifteen minutes.

## 2026-08-28 — D020: Practitioner publications replace institutional sources

The professional-publication portfolio uses bounded public DEV.to article API
queries and tag RSS feeds, plus exact operator-approved Hashnode RSS feeds.
DEV.to is the launch discovery source; Hashnode GraphQL is excluded because it
is not a public broad-discovery interface and intake holds no Hashnode
credential. Community material remains untrusted discovery input, and factual,
legal, security, performance, or product claims require independent primary
evidence before promotion.
