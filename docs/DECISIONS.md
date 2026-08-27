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
