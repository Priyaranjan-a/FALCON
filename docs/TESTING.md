# Testing and verification

FALCON is verified at four levels:

- server tests;
- console checks;
- validation of every export against its official standard;
- end-to-end runs of the real application.

## Run the checks

```sh
# Server (from server/): unit, API, engine and CLI tests
.venv/Scripts/python -m pytest        # Windows
.venv/bin/python -m pytest            # Linux and macOS

# Console (from console/): types, unit tests, production build
npx tsc -b && npx vitest run && npm run build
```

Continuous integration (`.github/workflows/ci.yml`) runs both on every push:

- the server tests on Linux, in the same Debian image the container ships,
  with OpenSSL 3.5;
- the console checks.

## Server tests

325 tests. API tests run against a fresh database built by the real
Alembic migrations, so the migration chain is exercised on every run.

| Area | Files | What is verified |
|---|---|---|
| Identity and access | `test_identity.py` | Setup, weak-password rejection, hardened session cookies, the cross-site request header check, lockout, sessions and other-device sign-out, single-use invitations, role enforcement, tokens, owner protection and recovery |
| Audit ledger | `test_ledger.py` | Every change recorded and chained; tampering and truncation detected; concurrent writers never fork the chain; security headers |
| Systems and horizon | `test_systems.py`, `test_horizon.py` | Register validation, the CRQC model, Mosca per system, milestones |
| Discovery engine | `test_discovery_engine.py`, `test_names.py`, `test_endpoints.py`, `test_long_paths.py` | Every detector against the sample estates; name normalisation (JCA, OpenSSL, JOSE, TLS, SSH, IPsec, OIDs); the TLS probe; archive safety; deep container images on Windows |
| Discovery API | `test_discovery_api.py` | Sources, uploads, scans, live events, inventory, evidence, scan diffs |
| Risk | `test_risk_model.py`, `test_risk_api.py` | Roles, Mosca X/Y/Z, scoring, HNDL, policies, time-machine dates, threat-model changes re-pricing the estate |
| Migration | `test_migration.py` | Recommendations (TLS, SSH, IPsec, signatures, CAs, symmetric, CNSA sizing), waves, schedule, benchmarks, scan verification |
| Reporting | `test_reports.py` | CycloneDX structure and references, SARIF rules and locations, SPDX relationships, CSV injection safety, ML-DSA-65 attestation round trip, tampering, key rotation, drift, the reports API and permissions, the offline CLI |
| Export library | `test_exports.py` | Server library and desktop folders, file integrity, re-download, reveal, desktop-only operations |
| Schema and first run | `test_schema.py`, `test_demo.py` | The models match the migrations; a fresh `--demo` start seeds a working platform exactly once |
| Desktop engine | `test_desktop.py` | Loopback serving, readiness announcement, shutdown when the shell exits |

## Standards validation

The export formats were validated against the official schemas during
development:

| Output | Validator | Result |
|---|---|---|
| CycloneDX 1.6 CBOM, JSON | Official CycloneDX 1.6 JSON schema (with SPDX and JSF sub-schemas) | Valid |
| CycloneDX 1.6 CBOM, XML | Official CycloneDX 1.6 XSD | Valid |
| SARIF 2.1.0 | OASIS SARIF 2.1.0 JSON schema | Valid |
| SPDX 2.3 | `spdx-tools` (the SPDX project's validator) | Valid |
| ML-DSA-65 attestation | `openssl pkeyutl -verify` (OpenSSL 3.5, stock Alpine container) | Signature verified; a modified payload is rejected |

## End-to-end checks

The real application is exercised in a browser, with automated screenshots, in
light, dark and phone layouts. The runs cover:

- sign-in;
- every page, with zero console errors;
- navigation timing: about 32–47 ms from click to painted page, with no long
  tasks;
- exports, with files checked on disk;
- signing and verifying snapshots through the interface;
- keyboard shortcuts and rebinding;
- the loading indicator;
- the executive brief rendered to PDF.

The production container was run with a read-only root file system, all
capabilities dropped and a non-root user. Inside it, the checks covered setup,
the scan-root enforcement, a scan, and signing and verifying a snapshot.

The packaged Windows engine was checked in desktop mode:

- key generation, a signed scan and verification from the frozen executable;
- exports written to the chosen folder.

## Security testing highlights

- Every endpoint requires a named permission. Tests confirm what each role can
  and cannot do.
- State-changing requests need the `X-Falcon-Request` header. Cookies are
  `HttpOnly` and `SameSite=Strict`.
- Archive extraction rejects path traversal, symbolic links and archive bombs.
  Git clones run with hooks, submodules and credential helpers disabled.
- Secrets in scanned code are masked before findings leave the scan worker, and
  private-key material is never stored.
- On a server, exported files are integrity-checked before being served again.
- The audit ledger detects alteration, deletion, reordering and truncation.
