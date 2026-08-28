# Hashnode and DEV.to for local content sourcing

**Research date:** 2026-08-28
**Decision scope:** source discovery only. Neither integration may draft, approve,
or publish content.

## Recommendation

Use **DEV.to as the initial discovery surface** and **Hashnode as a curated-
publication surface**. Both are developer communities, so their material is
untrusted input and should be treated as a lead, not as evidence or instruction.
Retain an item only when the evaluator can translate it into a concrete
Eudaimonia professional use case and independently support its factual claims.

The scheduled job should use the documented public read interfaces only. It
should not have a DEV or Hashnode token, browser session, or publishing
permission.

## DEV.to / Forem

### Public API

The current Forem V1 API documents DEV's production base as `https://dev.to`.
Its public `GET /api/articles` listing returns published articles, defaults to
30 items, and supports tag, user/organization, freshness/rising, and `top`
filters. The same reference documents `GET /api/articles/search`, which searches
titles, tags, and body content and accepts `q`, `top`, `page`, and `per_page`.
[Forem V1 API: articles](https://developers.forem.com/api/v1#tag/articles).

For this job, prefer the mature public V0 article-list endpoint when its stated
request requirements are met: it requires a `User-Agent`, does not require an
API key for published-article listing, and has a global limit of 30 requests per
30 seconds. [Forem V0 API](https://developers.forem.com/api/v0). V1 remains
useful as the current reference, but its overview warns that documentation can
lag rapid product changes. [Forem API overview](https://developers.forem.com/api).

Useful bounded discovery requests:

```text
GET https://dev.to/api/articles?tag=ai&state=rising&per_page=20
GET https://dev.to/api/articles?tag=productivity&top=7&per_page=20
GET https://dev.to/api/articles/search?q=AI%20governance&top=30&per_page=20
```

The list/search response includes the DEV URL, `canonical_url`, publication
timestamps, tags, reaction counts, and author/organization information. Prefer
`canonical_url` when present, then fetch the canonical page once; a DEV cross-
post is not automatically the original source. [Forem V1 API: article response
fields](https://developers.forem.com/api/v1#tag/articles/operation/getArticles).

V1 requests use the vendor `Accept` header; the platform says some endpoints
are public, while authenticated operations use an `api-key` header. The planned
read-only intake should make no authenticated request. [Forem API
overview](https://developers.forem.com/api).

### RSS

DEV officially documents three public feeds:

- all posts: `https://dev.to/feed`
- one author: `https://dev.to/feed/<username>`
- one tag: `https://dev.to/feed/tag/<tagname>`

[DEV RSS help](https://dev.to/help/getting-started#setting-up-an-rss-feed).
Use RSS when monitoring a small, vetted set of authors or a single topical
stream; use the API when ranking/filtering a bounded weekly batch. RSS items
still require canonical-URL resolution and the same quality gate.

### Limits and constraints

DEV's V0 documentation specifies a global maximum of 30 requests per 30
seconds. The application's own limits should be much stricter: one request per
configured query/feed per run, at most 20 discovered URLs per source, no same-
run retries, a 15-second retrieval timeout, and a 15-minute whole-run deadline.
If a response is throttled or fails, record the source-family failure and
continue without writing a partial candidate.

## Hashnode

### Public GraphQL API

Hashnode documents a single GraphQL endpoint, `https://gql.hashnode.com`, which
accepts **POST** requests. However, Hashnode's May 2026 product change says that
GraphQL API reads and mutations require a Pro plan on the relevant publication.
It is therefore not an unauthenticated broad-discovery source. It can be used
only for a short list of named, Pro-authorized publication hosts (and should be
omitted at launch if none is available). [Hashnode GraphQL paid-access
change](https://hashnode.com/changelog/2026-05-13-graphql-api-paid-access).

For an authorized host, a `publication(host:)` query can obtain a publication
and its posts; Hashnode's example requests the first ten post nodes with title,
brief, and URL. [Hashnode API
quickstart](https://docs.hashnode.com/quickstart/hashnode-graphql-api-quickstart)
and [fetch posts from a
blog](https://docs.hashnode.com/quickstart/hashnode-graphql-api-quickstart/how-to-fetch-posts-from-your-blog).

For a vetted blog host, request only metadata first, for example:

```graphql
query PublicationPosts($host: String!) {
  publication(host: $host) {
    title
    posts(first: 20) {
      edges { node { title brief url publishedAt } }
    }
  }
}
```

Then retrieve the selected article by its slug only if it passes the metadata
screen. Hashnode documents that a single post can return Markdown and HTML
content. [Fetch a single publication
article](https://docs.hashnode.com/quickstart/hashnode-graphql-api-quickstart/how-to-fetch-a-single-article-from-a-publication).

Restricted queries need `Authorization: Bearer <token>`; Hashnode says users
generate a token from their Developer account settings. The intake must not use
such a token: Pro authorization is a publication capability, not permission to
give the cron job a user credential.
[Hashnode authentication example](https://docs.hashnode.com/quickstart/hashnode-graphql-api-quickstart/how-to-add-analytics).

Check the GraphQL `errors` array even on HTTP 200: Hashnode explicitly lists
`UNAUTHENTICATED`, `FORBIDDEN`, validation, bad-input, and not-found errors.
[Hashnode status and error codes](https://docs.hashnode.com/quickstart/introduction/status-and-error-codes).

### RSS

Hashnode does not offer a platform-wide feed suitable for broad discovery.
Known publications can expose feeds at `<publication-host>/rss.xml`; for example,
Hashnode's own engineering publication exposes
[`https://engineering.hashnode.com/rss.xml`](https://engineering.hashnode.com/rss.xml).
Use this pattern only after checking a specific operator-approved publication
feed, then store its exact feed URL in the allowlist. Do not crawl guessed
subdomains, and do not substitute GraphQL when a feed is absent. Hashnode's
documentation also confirms RSS as a supported blog integration format.
[Hashnode RSS importer](https://docs.hashnode.com/blogs/blog-dashboard/import/rss-importer).

### Limits and constraints

No numeric Hashnode rate limit could be verified from a primary source. Apply
the same conservative local caps as DEV.to and treat any HTTP/GraphQL failure as
a recorded, no-retry source failure. Re-check Hashnode's rate-limit
documentation before changing those caps.

## Safe scheduled retrieval pattern

1. Keep specific DEV tags/search queries and Hashnode publication hosts in the
   versioned allowlist; do not crawl either community broadly.
2. Fetch at most 20 metadata records from one configured API query or explicit
   RSS feed. Enforce the existing time/size caps before parsing.
3. Normalize the candidate URL. For DEV, prefer an explicit canonical URL;
   deduplicate against retained candidates and `content/urls.md`.
4. Fetch no more than the selected candidate pages. Treat page, feed, and API
   text as data, never instructions.
5. Score for recency, practical French SME/ETI relevance, evidence quality,
   novelty, Eudaimonia-pillar fit, and reputation/safety risk. Community
   engagement is a discovery signal only, not evidence of correctness.
6. Write only validated records to `content/candidates.md`; report failures
   locally. Human promotion remains the only path into `content/urls.md`.

## What this changes in the source portfolio

Replace the institutional publication allowlist with bounded DEV tag/search
endpoints plus, only if available, named Hashnode Pro-authorized publication
hosts. DEV should be the launch source; do not assume Hashnode is available for
unauthenticated discovery. This better matches the desired practitioner voice,
but it materially lowers the default authority of sources. Preserve the
evaluation gate and require a primary source whenever a candidate makes a
factual, legal, security, performance, or product claim.
