# Local Social Publishing

This context turns reviewed source material into platform-specific social posts
and records their local or remote outcomes.

## Language

**Approved draft**:
A human-approved, immutable local package containing the final platform renderings
and image before publication is requested.
_Avoid_: Draft, scheduled post

**Publication**:
The creation of a platform post from an approved draft on behalf of the local
operator.
_Avoid_: Approval, export

**Publication receipt**:
A durable record of one platform's publication attempt and, when successful,
its remote post identity and URL.
_Avoid_: Manifest, log

**Publication outcome**:
The current delivery state for one approved draft on one platform: pending,
publishing, published, failed, or unknown.
_Avoid_: Approval state, job stage

**Image-complete publication**:
A publication whose remote platform post includes the exact approved image as
well as that platform's approved text.
_Avoid_: Text-only publication, attachment attempt

**Local operator**:
The single person who runs the CLI and authorizes their own social-platform
accounts through direct OAuth 2.0 developer APIs.
_Avoid_: User, tenant

**Local operator workspace**:
A loopback-only TypeScript interface through which the local operator reads the
persisted workflow and submits the same explicit commands available in the CLI.
_Avoid_: Remote dashboard, administration portal

**Review workspace**:
The focused local operator view of one human-review package, containing the
source provenance, platform-specific renderings, mandatory image, validation
evidence, and explicit review actions.
_Avoid_: Draft editor, publication scheduler

**Research intake**:
A local, opt-in process that discovers source candidates for the local operator;
it neither drafts nor publishes social content.
_Avoid_: Content automation, publishing agent

**Source candidate**:
An untrusted URL with its proposed editorial angle and audience, kept outside
the runnable URL queue until the local operator deliberately promotes it.
_Avoid_: Queue item, approved source

**Candidate portfolio**:
The bounded collection of source families eligible for research intake: public
GitHub repositories, public Reddit discussions, and operator-approved
professional publications.
_Avoid_: Open-web crawl, arbitrary sources

**Candidate promotion**:
The local operator's explicit, validated transfer of one source candidate into
the runnable URL queue.
_Avoid_: Automatic enqueueing, approval

**Candidate record**:
The auditable local entry for one source candidate: its provenance, grounded
evidence, proposed Eudaimonia angle, professional use case, audience, score,
and lifecycle status.
_Avoid_: Draft post, queue entry

**Candidate expiry**:
The transition of an unpromoted source candidate to an `expired` status after
thirty days; the record is retained for audit and cannot be promoted.
_Avoid_: Deletion, silent cleanup

**Candidate deletion**:
The local operator's irreversible removal of one active source candidate from
the candidate register after a two-step confirmation. Promoted candidates
remain retained because they have entered the runnable workflow.
_Avoid_: Queue deletion, post deletion, automatic cleanup

**Research source configuration**:
The versioned, operator-maintained allowlist of GitHub queries, subreddits, and
professional publications that the research intake may consult.
_Avoid_: Open-web search, implicit sources

**Intake run report**:
The local audit record of one research-intake run, including source families
consulted, retained candidates, and safely skipped failures.
_Avoid_: Publication receipt, runtime log

**Professional-use-case translation**:
The proposed, evidence-grounded explanation of how a source relates to a
concrete executive decision or business workflow for a French SME or ETI.
_Avoid_: Technical summary, draft copy

**Research intake bounds**:
The fixed time, retrieval, and evidence-size limits that make one intake run
finite and prevent a source from monopolising local resources.
_Avoid_: Best-effort crawl, unlimited research
