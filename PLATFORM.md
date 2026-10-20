# Product and platform direction

## Purpose
Film discovery.

## Public experience
Catalog and legal viewing links.

## Private boundary
Review storage and monitoring require deployment protection; static Pages cannot run Flask controls.

## Useful next actions
Saved-watch workflows with storage controls.

## Infrastructure
Separate public artifacts from backend secrets and private data. Use HTTPS and the existing documented build and deployment entry points.

## Release requirements
- Use least-privilege identities and deployment-secret storage.
- Repository visibility does not enforce application authorization.
- Require applicable CI checks and retain a recoverable release.
- Verify keyboard navigation, narrow screens, reduced motion and failed-network behavior.
- Document retention, deletion and backup recovery before collecting private data.
- Evaluate passkeys, offline synchronization and AI assistance against actual user needs. They are not universally implemented.
- GitHub settings, branch protection and visibility require exact targets and verification.

This describes architecture and direction, not proof that proposed features or deployment controls are delivered.
