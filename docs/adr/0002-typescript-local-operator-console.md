# TypeScript local operator console

The loopback workspace will become a React, Vite, and TypeScript single-page
application with Candidates, Intake, Pipeline, Review, and Outcomes pages. Its
prebuilt assets are packaged and served by the Python `social-agent workspace`
command, while the Python operator-workspace module remains the sole interface
for persisted reads and explicit workflow commands; this delivers a rich local
operator experience without a second state machine or remote control plane.

## Consequences

Node tooling is introduced only for frontend development, testing, and build;
the operator does not run a separate frontend server. The app retains loopback
binding, one operator, no sessions, and the existing immutable-approval and
X-before-LinkedIn publication boundary.
