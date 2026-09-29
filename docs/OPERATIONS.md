# Operations

FALCON installs four ways, all built from the same code:

| Install | For | Data |
|---|---|---|
| Desktop app (Windows installer) | One analyst on their own machine | `%APPDATA%\in.falcon.desktop` |
| Container (`Dockerfile`, `docker-compose.yml`) | A team server | the `/var/lib/falcon` volume |
| Python package (`pip install ./server`) | Bare-metal or VM servers | `FALCON_DATA_DIR` |
| Offline CLI (`falcon scan`) | CI pipelines and one-off audits | none: it writes only the report |

FALCON makes no outbound calls of its own. Fonts, knowledge bases and rule packs
are bundled, so it runs air-gapped. The only network traffic is what an
operator asks for: cloning a Git source, pulling a registry image, or probing a
TLS endpoint.

## First run and the demonstration

`scripts/start.ps1` (Windows) and `scripts/start.sh` (Linux and macOS) install
everything on first use and start FALCON with `--demo`. `docker compose up` does
the same. On a fresh installation the demo creates the following, then prints
the sign-in:

- the organisation *Example National Agency*, with a moderate threat model;
- an owner account;
- ten systems with realistic business context;
- scans of the bundled sample estates (a payments monorepo, an identity
  service, CA material and a container image);
- once the scans finish, a benchmark run and a signed first snapshot.

| | Default | Override before the first start |
|---|---|---|
| Email | `admin@falcon.local` | `FALCON_DEMO_ADMIN_EMAIL` |
| Password | `Quantum-Safe-2026!` | `FALCON_DEMO_ADMIN_PASSWORD` |

The demo never touches an installation that is already set up. For a clean
installation with the setup assistant, start with `-NoDemo` or `--no-demo`, or
run `falcon serve`.

## Desktop app

Run `FALCON_1.0.0_x64-setup.exe`. It is a per-user install and needs no
administrator rights. On first launch the setup assistant creates the
organisation, its threat model and the owner account.

Exports are saved to `Downloads\FALCON Exports`. You can change the folder in
**Reports → Exports** or **Settings → Exports & downloads**.

The engine runs on a random loopback port, only while the app is open. Its log
is in `%APPDATA%\in.falcon.desktop\logs\engine.log`. Build the installer from
source with `scripts\build-desktop.ps1`; this needs Python 3.12+, Node 20+ and
Rust with the MSVC toolchain.

## Container

```sh
docker compose up -d                                  # http://localhost:8600
FALCON_SCAN_DIR=/srv/code docker compose up -d        # make a folder scannable (read-only)
```

The image is built in two stages: the console is built with Node, then served by
Python 3.13 on Debian trixie. Trixie ships OpenSSL 3.5, which the post-quantum
TLS probe needs to negotiate X25519MLKEM768. The container:

- runs as an unprivileged user (UID 10001) with a read-only root file system;
- drops all capabilities and sets `no-new-privileges`;
- keeps state only in the `falcon-data` volume;
- has a health check on `/api/v1/setup`.

The same image is the CI scanner:

```sh
docker run --rm -v "$PWD:/work" -w /work falcon:1.0.0 scan . --format sarif --output falcon.sarif --fail-on high
```

**TLS.** In production, session cookies are `Secure`, so FALCON must be served
over HTTPS: put a reverse proxy such as nginx, Caddy or a load balancer in
front of port 8600. `localhost` works without TLS for evaluation.

## Configuration

Every setting is a `FALCON_`-prefixed environment variable, or a line in `.env`.

| Variable | Default | Meaning |
|---|---|---|
| `FALCON_ENVIRONMENT` | `development` | `production` enables Secure cookies and restricts folder scanning to `FALCON_SCAN_ROOTS` |
| `FALCON_HOST`, `FALCON_PORT` | `127.0.0.1`, `8600` | Listen address |
| `FALCON_DATA_DIR` | `./data` | Database, uploads, scan workspaces, attestation keys, benchmarks |
| `FALCON_DATABASE_URL` | SQLite in the data dir | e.g. `postgresql+psycopg://user:pass@host/falcon` (install `falcon-server[postgres]`) |
| `FALCON_SCAN_ROOTS` | `[]` | JSON list of folders a server may scan; uploads of archives and images are always allowed |
| `FALCON_ALLOW_NETWORK_PROBES` | off on servers | Allow live TLS endpoint probing |
| `FALCON_SCAN_WORKERS` | `2` | Concurrent scans, each in its own isolated process |
| `FALCON_SCAN_TIMEOUT_MINUTES` | `60` | Hard time limit per scan |
| `FALCON_SCAN_MAX_FILES`, `FALCON_SCAN_MAX_FILE_MB` | `200000`, `16` | Scan size limits |
| `FALCON_UPLOAD_MAX_MB` | `2048` | Largest archive or image upload |
| `FALCON_SESSION_IDLE_MINUTES`, `FALCON_SESSION_ABSOLUTE_HOURS` | `120`, `12` | Session expiry |
| `FALCON_LOGIN_MAX_FAILURES`, `FALCON_LOGIN_LOCKOUT_MINUTES` | `5`, `15` | Account lockout |
| `FALCON_REGISTRY_USERNAME`, `FALCON_REGISTRY_PASSWORD` | none | Default container-registry credentials |
| `FALCON_DEMO` | off (`serve --demo` turns it on) | Seed the demonstration on a fresh installation |
| `FALCON_DEMO_ADMIN_EMAIL`, `FALCON_DEMO_ADMIN_PASSWORD` | `admin@falcon.local`, `Quantum-Safe-2026!` | The demonstration owner account |
| `FALCON_DEMO_BENCHMARKS` | `true` | Run the benchmark lab once the demo scans finish |

Schema migrations run automatically at start-up; `falcon migrate` runs them
explicitly.

## Backup and restore

Everything FALCON knows is in the data directory:

- `falcon.db`, with its WAL files;
- `exports/`: exported files, on a server;
- `preferences.json`: the desktop export folder;
- `keys/`: the ML-DSA-65 attestation keys. **Keep this secret**; losing it
  means new snapshots are signed by a new key.
- `uploads/`: uploaded archives and images;
- `benchmarks.json`.

For a consistent SQLite copy while running:

```sh
sqlite3 /var/lib/falcon/falcon.db ".backup '/backup/falcon-$(date +%F).db'"
tar -C /var/lib/falcon -czf /backup/falcon-keys-$(date +%F).tgz keys
```

To restore, stop FALCON, put the files back, and start it. With PostgreSQL,
back up the database with `pg_dump` and keep `keys/` as above.

## Recovery

If the owner is locked out, an operator with shell access runs
`falcon recover-owner`. It revokes the owner's sessions and tokens and prints a
one-time sign-in link. The action is recorded in the audit ledger.

## Security posture

- **Identity:**
  - Argon2id passwords, account lockout and per-address rate limits.
  - Server-side sessions in `HttpOnly`, `SameSite=Strict` cookies, with a
    request header check against cross-site requests.
  - Personal access tokens for automation.
- **Authorisation:** six roles map to explicit permissions, and every endpoint
  checks a permission, never a role.
- **Audit:** every change, export, signature and key rotation is written in the
  same transaction as a SHA-256 hash-chained ledger event. The whole chain is
  verifiable from the console.
- **Scanning:**
  - Each scan runs in a separate process with time limits.
  - Archives are checked for bombs and path traversal.
  - Symbolic links are ignored.
  - Git hooks and submodules are disabled.
  - Secrets found in code are masked before they leave the worker; private-key
    contents are never stored.
- **HTTP:** strict Content Security Policy, `X-Content-Type-Options`,
  `Referrer-Policy`, frame denial, and RFC 9457 problem responses that never
  leak internals.
- **Evidence:** snapshots are signed with ML-DSA-65 and verifiable by third
  parties with OpenSSL 3.5.

## Command line

```text
falcon serve [--demo]             run the API and console (--demo: seed a fresh installation)
falcon migrate                    apply schema migrations
falcon recover-owner              one-time sign-in link for a locked-out owner
falcon scan PATH [options]        offline scan and report (see below)
falcon keygen --out DIR           ML-DSA-65 key pair for signing CBOMs in CI
falcon verify ENVELOPE --key PEM  verify a signed CBOM attestation
```

`falcon scan PATH` accepts a folder, an archive, a saved container image
(`docker save` or an OCI layout), a Git URL, or with `--endpoint` a list of
`host:port` TLS endpoints.

| Option | Meaning |
|---|---|
| `-f/--format` | `table` (default), `sarif`, `cyclonedx`, `cyclonedx-xml`, `spdx`, `csv`, `json` |
| `-o/--output` | Write the report to a file instead of standard output |
| `--fail-on` | `critical`, `high`, `medium`, `low`, `hndl`, `broken` or `never` (default) |
| `--sign-key` | ML-DSA-65 private key: also writes a DSSE attestation of the CBOM |
| `--criticality`, `--exposure`, `--classification`, `--shelf-life`, `--migration-years` | The system's context, which feeds impact and Mosca X and Y |
| `--scenario`, `--tolerance` | The threat model: Mosca Z |

Exit codes:

| Code | Meaning |
|---|---|
| 0 | Passed |
| 1 | The `--fail-on` gate tripped |
| 2 | Usage or scan error |
| 3 | Attestation verification failed |

### GitHub Actions

```yaml
name: Cryptography
on: [push, pull_request]
jobs:
  falcon:
    runs-on: ubuntu-latest
    permissions: { contents: read, security-events: write }
    steps:
      - uses: actions/checkout@v4
      - name: Discover and assess cryptography
        run: |
          docker run --rm -v "$PWD:/work" -w /work "$FALCON_IMAGE" \
            scan . --format sarif --output falcon.sarif --fail-on high
        env: { FALCON_IMAGE: "${{ vars.FALCON_IMAGE }}" }
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with: { sarif_file: falcon.sarif, category: falcon }
```

### GitLab CI

```yaml
falcon:
  image: $FALCON_IMAGE
  stage: test
  script:
    - falcon scan . --format cyclonedx --output cbom.cdx.json --sign-key "$FALCON_SIGNING_KEY"
    - falcon scan . --format sarif --output falcon.sarif --fail-on hndl
  artifacts:
    when: always
    paths: [cbom.cdx.json, cbom.cdx.json.dsse.json, falcon.sarif]
```

`FALCON_SIGNING_KEY` is a GitLab *file* variable holding the private key from
`falcon keygen`. Publish `falcon-attestation.pub.pem` wherever verifiers need it.
