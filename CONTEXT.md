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
