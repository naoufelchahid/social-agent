# Direct OAuth publication requirements for X and LinkedIn

**Research date:** 2026-08-28

**Decision scope:** Direct OAuth 2.0 publication to the local operator's personal
X and LinkedIn accounts, including one image. This records provider facts needed
for adapters and crash-safe publication; it does not add scheduling, remote
editing/deletion, threads, or organization-page publishing.

## Decision summary

Implement separate provider grants behind one publication interface. A grant
stores the provider account ID and display identity, exact granted scopes,
encrypted access/refresh credentials actually returned by the provider, and
their expirations. Refresh replaces the token set atomically; a missing or
unusable refresh path requires operator re-authorization.

Treat publication as successful only after the documented success response also
contains the provider's post ID. Treat a request as **known failed** only when it
was rejected before dispatch or a complete provider response definitively
rejects it. If dispatch may have happened but no provider post ID was durably
captured—including a timeout, connection loss, 5xx/504, or malformed success
response—the outcome is **unknown**. Do not automatically resend an unknown
create request: neither provider documents a client idempotency key or a
lookup-by-client-request-key operation, so retry can duplicate a post. This is a
conservative design inference from the official contracts, not a provider
guarantee.

## X contract

### Connection, scopes, and identity

Use OAuth 2.0 Authorization Code Flow with PKCE in user context. Generate a
fresh verifier/challenge and unpredictable `state`, verify `state` at callback,
require the callback URI to exactly match the registered URI, and exchange the
code at `POST https://api.x.com/2/oauth2/token`. X says the PKCE access token
lasts two hours by default; requesting `offline.access` returns a refresh token
for the same token endpoint. [X OAuth 2.0 Authorization Code Flow with
PKCE](https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code)
and [X user access-token
flow](https://docs.x.com/fundamentals/authentication/oauth-2-0/user-access-token).

Request exactly:

- `tweet.read`, `tweet.write`, and `users.read` for `POST /2/tweets` and
  `GET /2/users/me`;
- `media.write` for media upload; and
- `offline.access` for a durable local connection.

X assigns the first three scopes to post creation and account lookup and defines
the latter two for media upload and refresh. [X API v2 authentication
mapping](https://docs.x.com/fundamentals/authentication/guides/v2-authentication-mapping)
and [X OAuth scope
reference](https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code).

After connection and after a material token replacement, call user-context
`GET https://api.x.com/2/users/me`. Persist `data.id` as the stable provider
account ID plus `name` and `username` for operator confirmation. [X Get my
User](https://docs.x.com/x-api/users/get-my-user).

Store access tokens encrypted and refresh tokens with additional access
controls. Never put credentials in client code, logs, or the repository. [X
security guidance](https://docs.x.com/fundamentals/security). Persist expiry and
granted scopes alongside them; on refresh, atomically replace all token response
fields so a crash cannot leave a mismatched token set.

### Image and post creation

Upload first with `POST https://api.x.com/2/media/upload`, using a user token
with `media.write`, and retain returned `data.id` and expiry. X documents
`tweet_image`, a 5 MB image limit, and up to four photos per post. If
`processing_info` is present, wait at least `check_after_secs` and poll until
`state` is `succeeded`; do not post pending or failed media. [X upload
media](https://docs.x.com/x-api/media/upload-media), [media
introduction](https://docs.x.com/x-api/media/introduction), [media upload
status](https://docs.x.com/x-api/media/get-media-upload-status), and [media best
practices](https://docs.x.com/x-api/media/quickstart/best-practices).

Create with `POST https://api.x.com/2/tweets`, bearer user authorization, JSON
text, and `media.media_ids`. Confirm success only for HTTP 201 with parseable
`data.id`; persist that ID and returned text as the receipt before completing
publication. [X Create or Edit
Post](https://docs.x.com/x-api/posts/create-post) and [X Manage
Posts](https://docs.x.com/x-api/posts/manage-tweets/introduction).

X returns structured problem details. A complete 4xx response is a known
rejection; retain status, `type`, `title`, and `detail`. Although X generally
advises retrying 500/502/503/504 responses after waiting, that is unsafe for this
non-idempotent create when no post ID was captured; classify it as unknown for
operator reconciliation. [X response codes and
errors](https://docs.x.com/x-api/fundamentals/response-codes-and-errors).

## LinkedIn contract

### Connection, scopes, tokens, and identity

Use LinkedIn's three-legged OAuth 2.0 authorization-code flow. Validate `state`,
require a registered matching redirect URI, exchange the code at
`POST https://www.linkedin.com/oauth/v2/accessToken`, and store `expires_in`. A
local native client may use LinkedIn's documented PKCE loopback flow. [LinkedIn
3-legged OAuth
flow](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow)
and [OAuth for native
clients](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow-native).

Request `openid profile w_member_social`. `w_member_social` is the open,
self-service permission for posting as the authenticated member; `openid
profile` supplies the member subject and display profile. Do not request `email`
because publication does not need it. [Getting access to LinkedIn
APIs](https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access)
and [LinkedIn
OIDC](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2).

Validate the ID token against LinkedIn's discovery metadata/JWKS or call
`GET https://api.linkedin.com/v2/userinfo`; persist `sub`, name, and picture.
Use the member ID as author `urn:li:person:{member-id}` and show that profile to
the operator before enabling publication. [LinkedIn
OIDC](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2)
and [Share on
LinkedIn](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin).

LinkedIn access tokens report `expires_in` and currently last 60 days.
Programmatic refresh tokens are available only to approved Marketing Developer
Platform partners; when enabled, the documented defaults are 60 days for access
and one year for refresh, and use does not extend the refresh token's original
expiry. A self-service adapter must not assume a refresh token exists: persist
refresh fields only if returned for this app, otherwise reconnect through the
authorization flow. [LinkedIn authorization-code
flow](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow)
and [LinkedIn programmatic refresh
tokens](https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens).

### Image and post creation

Use the current Images API, not replaced Assets API. Initialize with
`POST https://api.linkedin.com/rest/images?action=initializeUpload`, owner set
to the connected Person URN, and capture `value.uploadUrl`, its expiry, and
`value.image`. Upload bytes to that URL, then reference the Image URN in
`content.media.id`. The API documents JPG, GIF, and PNG below 36,152,320 pixels
and does not support synchronous upload. [LinkedIn Images
API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/images-api).

There is a least-privilege constraint: the Images API says `w_member_social` is
write-only and a token with only that permission cannot GET the versioned image
resource, even though its model exposes states such as `WAITING_UPLOAD` and
`AVAILABLE`. Do not depend on status polling that the grant cannot perform.
Require a definite successful binary-upload response before post creation; if
upload completion is ambiguous, initialize/upload a fresh image rather than
advance to post creation. Re-uploading may orphan media but cannot duplicate a
public post.

Create with `POST https://api.linkedin.com/rest/posts`, author set to the Person
URN, `lifecycleState: PUBLISHED`, and intended visibility/main-feed
distribution. Include `Authorization`, `X-Restli-Protocol-Version: 2.0.0`,
`Content-Type: application/json`, and supported `Linkedin-Version: YYYYMM`. As
of the research date the latest documented version is `202608`; versions ship
monthly and remain supported for at least one year, so upgrade deliberately
before sunset. [LinkedIn Posts
API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api)
and [LinkedIn API
versioning](https://learn.microsoft.com/en-us/linkedin/marketing/versioning).

Confirm success only for HTTP 201 with parseable `x-restli-id`; persist that
post URN as the receipt before completing the command. A complete 4xx response
with `message`, `serviceErrorCode`, and `status` is a known rejection. LinkedIn
describes 500 as internal error and 504 as processing timeout and recommends
retry patterns generally; for post creation, classify either—or response
loss—as unknown because no idempotency key is documented. Retain safe request
diagnostic headers for support, never credentials. [LinkedIn Posts
API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api)
and [LinkedIn API error
handling](https://learn.microsoft.com/en-us/linkedin/shared/api-guide/concepts/error-handling).

## Adapter and recovery implications

| Result | Required evidence | Automatic next action |
| --- | --- | --- |
| `published` | Documented success and provider post ID | Persist receipt; complete command |
| `known_failed` | Proven no dispatch, or complete definitive rejection | Persist error; permit a new explicit attempt after correction |
| `unknown` | Dispatch may have occurred but no provider post ID | Persist diagnostics; block automatic resend |

Persist the immutable approved manifest and durable command before the first
provider call. Record attempt start, provider/account, request digest, media
IDs, timestamps, HTTP status, safe diagnostics, and provider post ID in the same
durable workflow authority. Never infer success from 2xx alone, and never turn
unknown into failed merely because the process restarted. A later
operator-authorized retry is a new attempt linked to the unknown one and must
display the duplicate-publication risk.
