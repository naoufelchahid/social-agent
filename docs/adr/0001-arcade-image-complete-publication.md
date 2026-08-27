# Arcade image-complete publication after approval

The local CLI will evolve from a draft-only application into a single-operator
publisher. Human acceptance remains the sole approval gate and immediately
publishes the immutable approved package to the operator's personal X and
LinkedIn accounts through direct Arcade SDK calls. Both posts must include the
approved image; the LinkedIn path therefore uses a private custom Arcade tool.
Publication outcomes and receipts are stored separately from the approval
manifest, with X published before LinkedIn. Known no-write failures retry only
their platform, while unknown outcomes require explicit operator resolution to
avoid duplicate posts.

## Consequences

Arcade Cloud and a stable locally stored Arcade operator ID are required. OAuth
authorization is performed by a separate `connect` command, not during
approval. Scheduling, analytics, editing or deleting remote posts, threads,
organization pages, and additional platforms remain out of scope.
