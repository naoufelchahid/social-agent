# Research intake sources

This file is operator-controlled configuration, not agent instructions. The
research intake may consult only the sources listed here.

## GitHub API search queries

- `topic:llm stars:>=100 pushed:>=2026-07-29`
- `topic:ai-agents stars:>=100 pushed:>=2026-07-29`
- `topic:workflow-automation stars:>=100 pushed:>=2026-07-29`
- `topic:artificial-intelligence stars:>=100 pushed:>=2026-07-29`

Use GitHub's public Search API only. Do not scrape the Trending webpage.

## Reddit communities

- `r/ArtificialInteligence`
- `r/MachineLearning`
- `r/LocalLLaMA`
- `r/AI_Agents`

Use public posts and discussions only. A discussion is eligible only if its
evidence supports a concrete professional-use-case translation.

## Professional publications

### DEV.to

- API: <https://dev.to/api/articles?tag=ai&state=rising&per_page=20>
- API: <https://dev.to/api/articles?tag=productivity&top=7&per_page=20>
- API search: <https://dev.to/api/articles/search?q=AI%20governance&top=30&per_page=20>
- RSS: <https://dev.to/feed/tag/ai>
- RSS: <https://dev.to/feed/tag/productivity>

Use only one request per configured API query or feed per run. Prefer a returned
canonical URL over a DEV cross-post URL, then retrieve the canonical page once.

### Hashnode

- RSS: <https://engineering.hashnode.com/rss.xml>

Use only these exact, operator-approved RSS feed URLs. Do not crawl Hashnode
subdomains or use its GraphQL API: GraphQL access is not a public broad-
discovery interface and intake has no Hashnode credential.
