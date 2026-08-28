# Secure credential storage for local OAuth grants

**Research date:** 2026-08-28
**Decision scope:** persistent local storage for independent X and LinkedIn
OAuth grants, with an explicit process-memory fallback and no secrets in
workflow snapshots or SQLite.

## Recommendation

Use `keyring` 25.7.x behind an application-owned `CredentialStore` interface.
Give each platform one versioned, stable key such as
`social-media-agent/oauth/x/v1` and
`social-media-agent/oauth/linkedin/v1`, with a fixed non-secret account name.
Store the complete grant as one compact JSON value so token rotation does not
create a mixed access-token/refresh-token pair.

Accept only a recommended, secure operating-system backend. Treat the failing
backend, the null backend, a non-recommended backend, initialization failure,
lock denial, and write failure as **secure storage unavailable**. Retain a
newly obtained grant only in the current process's memory in those cases and
show a persistent, safe `session only; reconnect after restart` warning. Do not
install or automatically accept `keyrings.alt`, and do not silently turn a
missing credential into fallback mode.

This gives the project a maintained Python API over macOS Keychain, Windows
Credential Manager, and Linux Secret Service while keeping policy, failure
translation, tests, and secret redaction inside the workflow module.

The platform-specific lower-level APIs remain available (`SecretStorage` on
Linux, Security Framework on macOS, and `win32cred` on Windows), but adopting
them directly would leave this application to maintain three implementations.
`keyring` already uses those native capabilities and exposes their common
service/account/value shape, while still allowing the application to own the
stricter policy this product needs.

## Verified capabilities

The latest published release is
[`keyring` 25.7.0](https://github.com/jaraco/keyring/releases/tag/v25.7.0),
released 2025-11-16. The project classifies itself as production/stable and
supports Python 3.9+, which includes this repository's Python 3.11+ baseline.
Its package metadata declares Windows `pywin32-ctypes` and Linux
`SecretStorage`/`jeepney` dependencies with platform markers.
[`keyring` 25.7.0 package metadata](https://github.com/jaraco/keyring/blob/v25.7.0/pyproject.toml).

The documented recommended backends are macOS Keychain, Freedesktop Secret
Service (including GNOME), KDE KWallet, and Windows Credential Locker. The
common API stores, reads, and deletes a Unicode secret by `(service, username)`;
an absent item returns `None` from `get_password`.
[`keyring` stable documentation](https://keyring.readthedocs.io/en/stable/).
That composite lookup is enough to keep the X and LinkedIn grants independent.
Using a distinct service value per platform also avoids the Windows backend's
multi-username collision compatibility logic.
[`keyring` Windows backend](https://github.com/jaraco/keyring/blob/v25.7.0/keyring/backends/Windows.py).

The platform implementations use the native stores:

- The macOS backend calls Security Framework generic-password operations and
  maps access denial to `KeyringLocked`, other writes to `PasswordSetError`,
  and other reads to `KeyringError`.
  [`keyring` macOS backend](https://github.com/jaraco/keyring/blob/v25.7.0/keyring/backends/macOS/__init__.py).
  Apple describes Keychain as an encrypted database for small secrets and
  identifies service plus account as generic-password primary keys.
  [Apple Keychain Services](https://developer.apple.com/documentation/security/keychain-services/)
  and [generic-password uniqueness](https://developer.apple.com/documentation/security/errsecduplicateitem).
- The Windows backend writes `CRED_TYPE_GENERIC` records through Windows
  Credential Manager with enterprise persistence by default.
  [`keyring` Windows backend](https://github.com/jaraco/keyring/blob/v25.7.0/keyring/backends/Windows.py).
- The Linux Secret Service backend checks that SecretStorage is installed and
  that a Secret Service daemon is running or activatable through D-Bus. It maps
  collection setup failure to `InitError` and a dismissed/failed unlock to
  `KeyringLocked`.
  [`keyring` Secret Service backend](https://github.com/jaraco/keyring/blob/v25.7.0/keyring/backends/SecretService.py).
  The underlying specification says the service runs in the user's login
  session, usually encrypts stored secrets, may require user unlock, and does
  **not** treat lookup attributes as secret material.
  [Freedesktop Secret Service specification](https://specifications.freedesktop.org/secret-service/latest-single/).

Linux packaging cannot guarantee runtime availability: even with Python
dependencies installed, a desktop Secret Service and usable D-Bus login
session must exist. Headless environments require explicit daemon, unlock, and
D-Bus setup; otherwise session-memory operation is the intended product
behavior, not a plaintext file substitution.
[`keyring` headless Linux guidance](https://keyring.readthedocs.io/en/stable/#using-keyring-on-headless-linux-systems).

The library's macOS security note says any Python code run by the same Python
executable can access secrets that executable created unless the operator
tightens the item's Keychain access control. This is acceptable only within the
confirmed single-user, local-process trust boundary; it is not application
sandbox isolation.
[`keyring` security considerations](https://keyring.readthedocs.io/en/stable/#security-considerations).

## Failure and fallback contract

`keyring` defines a common `KeyringError` base plus `InitError`,
`PasswordSetError`, `PasswordDeleteError`, `KeyringLocked`, and
`NoKeyringError`.
[`keyring` error definitions](https://github.com/jaraco/keyring/blob/v25.7.0/keyring/errors.py).
When discovery finds no viable backend, the library selects `fail.Keyring`,
whose every operation raises `NoKeyringError`.
[`keyring` backend selection](https://github.com/jaraco/keyring/blob/v25.7.0/keyring/core.py)
and [failing backend](https://github.com/jaraco/keyring/blob/v25.7.0/keyring/backends/fail.py).

There is also an explicitly configurable null backend whose reads, writes, and
deletes all return `None`. It is intended to disable keyring.
[`keyring` null backend](https://github.com/jaraco/keyring/blob/v25.7.0/keyring/backends/null.py).
Therefore the adapter must reject null/fail and any backend that is not an
allowlisted recommended OS backend before accepting a write. Merely catching
`PasswordSetError`, or treating a non-throwing `set_password` as proof of
persistence, is insufficient.

The application contract should distinguish these outcomes:

| Outcome | Meaning | Product behavior |
| --- | --- | --- |
| `get` returns a value | Persistent grant found | Deserialize and use it in memory; never copy it to workflow state. |
| `get` returns `None` | No grant exists for that platform | Show disconnected; this is not a storage failure. |
| Backend rejected or `get` raises | Secure storage unavailable/locked | Show a safe actionable error and allow a new OAuth grant to live in session memory only. |
| `put` succeeds | Grant accepted by secure backend | Read it back and compare before reporting persistent connection. |
| `put` raises or verification differs | Persistence failed | Keep the just-issued grant in process memory and report session-only connection. |
| `delete` raises | Persistent grant may remain | Do not report a completed disconnect; clear no durable connection state until deletion succeeds. |

Catch `KeyringError` for the library's normalized failures and defensively
translate unexpected backend exceptions at the adapter boundary. Log only the
exception class and a redacted, operator-safe category; backend messages are
not part of the browser contract. A locked store is unavailable for the
operation, but it is distinct from an absent credential and should remain
retryable.

The memory fallback is process-scoped and never writes a file, environment
variable, SQLite row, log field, command receipt, or browser payload. It starts
empty on every workspace process and is separate per platform. A successful
secure-store read may be held in memory for immediate provider use, but the
fallback itself must not imply persistence.

## Size and serialization constraint

Windows limits `CREDENTIAL.CredentialBlobSize` to
`CRED_MAX_CREDENTIAL_BLOB_SIZE`, 5 x 512 = **2,560 bytes**.
[Microsoft `CREDENTIAL` reference](https://learn.microsoft.com/en-us/windows/win32/api/wincred/ns-wincred-credentiala).
Because `keyring` writes a generic credential blob, the application cannot
assume an arbitrarily large serialized OAuth response will persist on every
platform. Serialize only the fields required to refresh and publish, use
compact JSON without base64 expansion, and measure its UTF-16LE byte length
(the Windows backend writes UTF-16) before a Windows write. If the complete
grant exceeds the native limit, fail the secure write as unavailable and
retain the grant in session memory; do not split a rotating grant into
independently updated secrets unless a later design also defines crash-safe
versioning.

## Adapter and test seam

Define the workflow-facing interface in project terms rather than exposing
`keyring` globally, for example:

```text
CredentialStore.load(platform) -> OAuthGrant | None
CredentialStore.save(platform, grant) -> StorageMode
CredentialStore.delete(platform) -> None
CredentialStore.status(platform) -> persistent | session_only | unavailable
```

The production adapter owns key naming, JSON schema/version checks, backend
allowlisting, size checks, error translation, read-after-write verification,
and redaction. The in-memory test adapter implements the same interface with
independent platform slots and programmable load/save/delete failures. Avoid
using `keyring.set_keyring()` as the main test seam: it changes process-global
library state, while the documented backend base class is simple enough to
wrap behind an injected project adapter.
[`KeyringBackend` interface](https://github.com/jaraco/keyring/blob/v25.7.0/keyring/backend.py).

Required offline cases are:

1. X and LinkedIn values never overwrite one another.
2. Persistent save plus workspace reconstruction loads the same grant.
3. No stored value is reported as disconnected, not unavailable.
4. Backend discovery/init, lock, save, verification, and delete failures map to
   explicit safe states.
5. A save failure preserves the newly issued grant only until process teardown.
6. A null, failing, non-recommended, or unknown backend is rejected.
7. An oversized Windows payload uses session memory without partial durable
   writes.
8. Grant rotation replaces one complete serialized value.
9. Snapshot, command receipt, logs, SQLite fixtures, and HTTP responses contain
   no access token, refresh token, authorization code, PKCE verifier, client
   secret, or serialized grant.

## Secret-free snapshot boundary

Only these derived, non-secret facts should cross into SQLite or
`WorkflowSnapshot`: platform, application-configured flag, connection state,
storage mode (`persistent` or `session_only`), provider account identity needed
by the operator, granted-scope names, expiry/readiness timestamps when useful,
and a redacted actionable error category. Credential-store service names are
non-secret lookup attributes, but exposing them provides no operator value and
should remain internal.

The snapshot must never contain access or refresh tokens, the full token
response, authorization codes, PKCE verifier/challenge material, client
secrets, raw credential-store exceptions, or a reversible credential
reference. This matches the Secret Service warning that lookup attributes may
be stored unencrypted and Apple's guidance that keychain items are intended for
small secret data rather than general application state.
