# API

Everything the console does goes through a REST API under `/api/v1`, and so
can scripts and other tools. A running FALCON serves interactive documentation
at **`/api/docs`**. The full OpenAPI 3.1 description is also in this
repository: [`api/openapi.json`](api/openapi.json) (85 operations).

## Authentication

| Method | For | How |
|---|---|---|
| Session cookie | The console | `POST /api/v1/auth/sign-in` sets an `HttpOnly`, `SameSite=Strict` cookie (`__Host-falcon_session` over HTTPS) |
| Personal access token | Scripts and pipelines | Create one in *Settings → Access tokens*, then send `Authorization: Bearer flc_…`. It carries the permissions of its owner's role |

State-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`) made with a session
cookie must include the header `X-Falcon-Request: 1`. Browsers cannot add it
cross-site, which blocks cross-site request forgery.

Every endpoint requires a named permission, such as `inventory.read`,
`scans.run` or `reports.sign`. `GET /api/v1/members/roles` lists the roles and
their permissions.

Errors are RFC 9457 problem documents:

```json
{ "type": "https://falcon.local/problems/unauthenticated", "title": "Authentication required",
  "status": 401, "detail": "Sign in to continue.", "code": "unauthenticated" }
```

## Endpoints by area

| Area | Main operations |
|---|---|
| Setup and platform | `GET/POST /setup` (first run), `GET /platform/health`, `GET /platform/about` |
| Authentication | Sign in and out, the current user, password, sessions (list, revoke others), invitation activation |
| Members and tokens | Invite, change role, suspend, reissue invitations; create and revoke access tokens |
| Organisation and horizon | Profile, threat model (`PUT /organisation/threat-model`), CRQC horizon, evaluation, regulatory milestones |
| Systems | Register, list with filters, detail, update, delete, vocabulary, summary |
| Discovery | Sources per system (folder, archive, Git, image, registry, endpoints; `…/sources/upload` for files); scans, cancel, **`GET /scans/{id}/events` (Server-Sent Events)**, scan diff; artefacts and inventory summary |
| Risk | `GET /risk/summary`, `/risk/register` (filters and sorting), `/risk/artefacts/{id}`, `/risk/timeline`, `/risk/policies` |
| Migration | `GET /migration/recommendations/{artefact}`, `/migration/plan`, `/migration/graph` (blast radius), benchmarks (read and run) |
| Reports | Formats; `GET /reports/export?format=` (direct download); the export library (`/reports/exports`, file, reveal, location); signed snapshots (create, list, verify, download CBOM or DSSE envelope); drift; the attestation key (`/reports/key`, `/reports/key.pem`, rotate); `POST /reports/verify` |
| Audit ledger | `GET /audit` (filters, paging), `POST /audit/verify` (re-check the hash chain) |

## Examples

With a personal access token in `$TOKEN`:

```sh
# The risk register, riskiest first
curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8600/api/v1/risk/register?sort=score&limit=20"

# Export the CycloneDX CBOM for the whole estate
curl -s -H "Authorization: Bearer $TOKEN" -o cbom.cdx.json \
  "http://127.0.0.1:8600/api/v1/reports/export?format=cyclonedx-json"

# Sign a snapshot of the current inventory (needs reports.sign)
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"label": "Quarterly baseline"}' http://127.0.0.1:8600/api/v1/reports/snapshots

# Follow a scan live
curl -N -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8600/api/v1/scans/<scan-id>/events
```

## Offline command line

For pipelines that should not call a server, the same engine runs offline:
`falcon scan`, `falcon keygen` and `falcon verify`. See
[OPERATIONS.md](OPERATIONS.md#command-line).
