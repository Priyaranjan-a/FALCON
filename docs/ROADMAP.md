# FALCON — Delivery Roadmap

FALCON is delivered in five phases. Each phase ends in a working, tested
platform. A new phase starts only after the previous one is reviewed and
approved. All five phases are complete.

| Phase | Name | Outcome |
|---|---|---|
| **1** | **Foundation** (complete) | Architecture, secure identity and access, organisation and systems register, quantum threat horizon, the design system, the **Falcon Viz** engine and the application shell |
| **2** | **Discovery Engine & Desktop** (complete) | Detector framework, scanning of source repositories, binaries, libraries, container images, certificates, keys, protocol configuration, live TLS endpoints and cloud KMS; live scan streaming; the cryptographic artefact inventory; FALCON as installable desktop software (Tauri) |
| **3** | **Quantum Risk Intelligence** (complete) | Classification by type, lifetime and criticality; per-artefact and per-system Mosca analysis; harvest-now-decrypt-later exposure; policy mapping (NIST IR 8547, SP 800-131A, CNSA 2.0); the **Quantum Time Machine** |
| **4** | **PQC Migration Planning** (complete) | Recommendation engine (risk profile, latency, cost, compatibility); hybrid options; on-host PQC benchmark lab; migration roadmap and waves; dependency blast-radius graph; what-if simulator; before/after verification |
| **5** | **CBOM, Reporting & Hardening** (complete) | CycloneDX 1.6 CBOM (JSON/XML), SPDX, SARIF, CSV; **ML-DSA-signed CBOM attestations**; CBOM drift; executive reports; CI/CD gate and CLI; container deployment; full documentation and hardening |

## Phase 1 — Foundation (scope)

### Server (`server/`)
- Domain-oriented FastAPI service: `kernel/` (database, security, access, audit,
  problems, HTTP hardening) and `domains/` (identity, organisation, systems,
  horizon, audit, platform).
- Alembic migrations applied automatically at start-up; SQLite (WAL) by default,
  PostgreSQL through `FALCON_DATABASE_URL`.
- Identity: first-run setup, server-side sessions in `HttpOnly` +
  `SameSite=Strict` cookies, CSRF header check, Argon2id passwords, account
  lockout, per-IP rate limiting, session management (sign out other devices),
  personal access tokens, member invitations with one-time activation links.
- Access control: six roles mapped to explicit permissions.
- **Tamper-evident audit ledger**: every event is SHA-256 hash-chained to the
  previous one, written in the same transaction as the change it records, and
  verifiable end-to-end from the console.
- Systems register: applications, products and infrastructure with business
  criticality, data classification, data shelf-life (Mosca X), migration time
  (Mosca Y) and exposure.
- Quantum threat horizon: probabilistic CRQC arrival model (scenario presets
  and custom), risk-tolerance planning year (Mosca Z), probabilistic Mosca per
  system, regulatory milestone catalogue.
- Errors follow RFC 9457 (`application/problem+json`).

### Console (`console/`)
- Design system: tokens (light/dark), typography, motion, and the component
  library.
- **Falcon Viz**: measurement, scales, axes, grid, crosshair, tooltip, legend,
  accessible table view, and the Phase 1 charts (probability curve, Mosca
  chart, capacity meter, rings, bar list, timeline, sparkline).
- Application shell: sidebar, toolbar, command palette (⌘K / Ctrl+K), theme.
- Screens: setup assistant, sign in, invitation activation, overview, systems
  register and system detail, threat horizon, settings (organisation, threat
  model, members, access tokens, sessions, audit ledger, appearance).

## Phase 2 — Discovery Engine & Desktop (complete)

### Model
- **Systems → Sources → Scans → Artefacts → Occurrences.** A source is something
  scannable that belongs to a system. An artefact is one cryptographic asset,
  de-duplicated across a system by a stable fingerprint. An occurrence is the
  evidence for it in one scan (path, line, detector, confidence).
- The seven artefact classes named by the problem statement: algorithm, key,
  certificate, protocol, library, hardware module and cloud service. Artefacts
  link to one another (a certificate uses a key and a signature algorithm).

### Engine
- Scans run in an isolated worker process: a malformed binary cannot take down
  the server, and cancellation and time limits are enforced by the parent.
- Sources: folders, archives (zip/tar), Git repositories, container images
  (saved tarballs or registry pulls) and live TLS endpoints.
- Safe acquisition: archive-bomb and path-traversal limits, symlinks ignored,
  Git hooks and prompts disabled, and allow-listed scan roots in server mode.
- A name grammar that normalises how cryptography is written in code and
  configuration (JCA, OpenSSL, JOSE, TLS and SSH names, IPsec proposals, X.509
  OIDs) into one algorithm catalogue with parameters and quantum status.
- Detectors: source code (Python syntax tree plus rule packs for C/C++, C#, Go,
  Java/Kotlin, JavaScript/TypeScript, PHP, Python, Ruby, Rust and Swift),
  dependencies and lockfiles, binaries (linkage, version strings and crypto
  constant signatures), Java classes and archives, certificates and keystores,
  keys (secrets never stored), protocol configuration (TLS, SSH, IPsec, cloud
  load-balancer policies), infrastructure-as-code KMS keys, and hardware
  modules (PKCS#11, TPM, cloud HSM).
- **Post-quantum TLS probe**: a hand-built TLS 1.3 ClientHello offering the
  hybrid X25519MLKEM768 group with a genuine ML-KEM key reveals whether an
  endpoint negotiates post-quantum key exchange.
- Live progress streamed to the console over Server-Sent Events.

### Console
- Sources on each system, the add-source flow, the live scan view with a
  coverage treemap, the scans list, the artefact inventory and artefact detail
  with evidence.

### Desktop
- A Tauri shell that starts the FALCON engine locally, opens the console in a
  native window and uses the native folder picker; built into a Windows installer.

## Phase 3 — Quantum Risk Intelligence (complete)

- **Risk model** (`server/falcon/risk/`):
  - roles derived from kind, primitive and observed usage;
  - Mosca X, Y and Z per artefact;
  - impact × likelihood, with classical, quantum and policy drivers;
  - bands;
  - harvest-now-decrypt-later exposure by reach;
  - classification by type, lifetime, criticality and Mosca state;
  - the years each artefact becomes at risk, exposed and broken.

  Weights live in `knowledge/risk.json`; the mathematics is in
  [METHODOLOGY.md](METHODOLOGY.md).
- **Policies:** NIST IR 8547, NIST SP 800-131A, CNSA 2.0 and the EU PQC roadmap,
  per artefact, with their dates and the rule applied.
- **API:** `/api/v1/risk/summary`, `/register`, `/artefacts/{id}`, `/timeline`
  and `/policies`, computed on read from the live inventory.
- **Console:**
  - Quantum Risk: bands, risk matrix, Mosca plane and register.
  - Quantum Time Machine: scrub to 2045.
  - Compliance.
  - Risk cards on artefacts and systems, and risk on the overview.
- **Design:** glass materials throughout, and a pointer light plus cursor on
  every clickable element.

## Phase 4 — PQC Migration Planning (complete)

- **Recommendation engine** (`migration/recommend.py`, `knowledge/pqc.json`).
  Each artefact gets:
  - a primary replacement, a hybrid and alternatives;
  - FIPS 203/204/205 sizes and the overhead on the wire;
  - steps and effort.

  Category 5 algorithms are used for secret, restricted or critical systems.
- **Benchmark lab:** ML-KEM-768/1024, ML-DSA-44/65/87, hybrid X25519MLKEM768
  and the classical algorithms they replace, timed on the host.
- **Plan:** five waves, a per-system roadmap, completion against the horizon,
  a blast-radius graph of shared cryptography, and a what-if simulator in the
  browser.
- **Verification:** a scan-to-scan diff showing what was retired, introduced,
  regressed, and where post-quantum cryptography spread.

## Phase 5 — CBOM, Reporting & Hardening (complete)

- **Writers** (`server/falcon/reporting/`), each validated against its official
  schema:
  - CycloneDX 1.6 CBOM in JSON and XML;
  - SARIF 2.1.0 (eight rules);
  - SPDX 2.3;
  - CSV and JSON.
- **Attestations:** an in-toto Statement v1 in a DSSE envelope, signed with the
  organisation's ML-DSA-65 key. Key rotation keeps old snapshots verifiable,
  and verification also works with OpenSSL 3.5.
- **Snapshots:** the `cbom_snapshots` table (migration 0003).
- **Drift:** between snapshots or against the live inventory.
- **API:** `/api/v1/reports/formats`, `/export`, `/snapshots`, `/drift`,
  `/key`, `/key.pem`, `/key/rotate` and `/verify`.
- **Permissions and audit:** a new `reports.sign` permission. Exports,
  signatures and rotations are audited under the new *reports* category.
- **Offline CLI:** `falcon scan` (folder, archive, image, Git or endpoints; seven
  output formats; `--fail-on` gates; `--sign-key`), plus `falcon keygen` and
  `falcon verify`.
- **Console:**
  - Reports: exports, signed snapshots with live verification, drift, the
    signing key, attestation upload and pipeline snippets.
  - Executive Brief: printable A4.
- **Motion:**
  - page code prefetched when idle, and data prefetched on hover;
  - no exit-phase delay between pages;
  - sections that rise in sequence on the compositor.

  Measured: 32–47 ms from click to painted page, with no long tasks.
- **Deployment:**
  - a `Dockerfile` (non-root, read-only root file system, health check,
    OpenSSL 3.5 base) and `docker-compose.yml`;
  - the `falcon` command installed with the package;
  - operations, methodology, architecture and reporting documentation.

## After Phase 5 — refinements

- **Export library.** Every export is written by the server and kept in a
  history.
  - Desktop: files go straight to a folder you choose (default
    `Downloads\FALCON Exports`), with Show in Folder and Open Folder.
  - Servers: files download through the browser, and a copy is kept to
    download again, byte for byte.
  - Available from a Safari-style downloads button in the toolbar and from
    **Settings → Exports & downloads**.
  - Migration 0004.
- **Flying-falcon loader.** It flies during page and data loads and circles
  the logo at start-up.
- **Interface sounds.** Web Audio, with a volume setting and previews.
- **Keyboard shortcuts.** One registry, rebindable in **Settings →
  Keyboard**, with a `?` overlay and `G`-sequences.
- **Appearance.** Seven accent colours and *Reduce transparency*.
- **Everything else:**
  - recent pages in the command palette;
  - a connection monitor;
  - window titles per page;
  - a skip-to-content link.
- **Builds.** One desktop build and one installer.
