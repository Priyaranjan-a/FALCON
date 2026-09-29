# Architecture

FALCON is one server process and a single-page console, packaged three ways:
a container, a Python package, and a Windows desktop app. The same engine also
runs offline as a command line for CI.

```
                ┌─────────────────────────── console (React 19, TypeScript) ──────────────────────────┐
                │ Overview · Systems · Horizon · Inventory · Scans · Quantum Risk · Time Machine ·     │
                │ Compliance · Migration Plan · Blast Radius · What-if · Benchmark Lab · Reports ·     │
                │ Executive Brief · Members · Audit Ledger · Settings          Falcon Viz (charts)     │
                └───────────────────────────────┬──────────────────────────────────────────────────────┘
                                                │ same-origin HTTPS, session cookie, SSE
┌───────────────────────────────────────────────▼───────────────────────────────────────────────────────┐
│ FastAPI  /api/v1                                                                                       │
│  identity · organisation · horizon · systems · discovery · risk · migration · reports · ledger          │
│  ─────────────────────────────────────────────────────────────────────────────────────────────────── │
│  kernel: database (SQLAlchemy 2, Alembic) · access (permissions) · audit (hash chain) · problems       │
│          (RFC 9457) · HTTP hardening (CSP, headers) · events (SSE hub)                                 │
└───────┬──────────────────────┬───────────────────────────┬───────────────────────────┬────────────────┘
        │ spawn (isolated)     │                           │                           │
┌───────▼────────┐    ┌────────▼─────────┐        ┌────────▼─────────┐        ┌────────▼─────────┐
│ discovery      │    │ risk             │        │ migration        │        │ reporting        │
│ engine         │    │ model · policies │        │ recommend · plan │        │ CycloneDX · SARIF│
│ acquire → walk │    │ Mosca · HNDL     │        │ bench (ML-KEM,   │        │ SPDX · CSV · JSON│
│ → detect       │    │ classification   │        │ ML-DSA timings)  │        │ ML-DSA-65 DSSE   │
└────────────────┘    └──────────────────┘        └──────────────────┘        │ drift            │
                                                                                └──────────────────┘
          knowledge/  algorithms · libraries · rule packs · risk · pqc · regulatory milestones (JSON)
```

## The pipeline

1. **Acquire.** A source (folder, archive, Git repository, container image,
   registry image or TLS endpoints) is materialised into a workspace. Limits
   are enforced throughout:
   - archive bombs and path traversal are rejected;
   - symbolic links are ignored;
   - Git hooks and submodules are disabled;
   - image layers are applied with whiteouts.
2. **Walk.** Files are classified by language and category. Coverage leaves are
   published so the console can draw the treemap before analysis starts.
3. **Detect.** Every file goes to the detectors that understand it:
   - Python syntax-tree analysis, plus rule packs for C/C++, C#, Go, Java/Kotlin,
     JavaScript/TypeScript, PHP, Python, Ruby, Rust and Swift;
   - manifests, lockfiles and OS package databases;
   - ELF, PE and Mach-O binaries, and Java bytecode;
   - certificates, keys and keystores;
   - TLS, SSH and IPsec configuration;
   - infrastructure-as-code KMS keys and HSMs;
   - the post-quantum TLS probe.

   Each finding names an algorithm in one catalogue and is assessed for
   classical and quantum strength. Secrets are masked before findings leave the
   worker.
4. **Consolidate.** Findings become artefacts, de-duplicated by a fingerprint
   of what they are. The evidence is kept as occurrences and the artefacts are
   linked to each other. An artefact the latest scans no longer see is marked
   resolved.
5. **Assess.** Risk is computed on read from the current artefacts, the
   systems register and the threat model, so it always reflects the latest
   scan and any change of assumptions. See [METHODOLOGY.md](METHODOLOGY.md).
6. **Plan.** Recommendations, waves, the roadmap, the blast-radius graph and the
   what-if simulator are all built on the assessment.
7. **Report.** Exports, signed snapshots and drift. See
   [REPORTING.md](REPORTING.md).

Steps 1–3 run in a separate process (spawned, not forked), so a malformed
binary cannot take the server down. The parent enforces cancellation and time
limits and streams progress to the console over Server-Sent Events. The offline
CLI runs the same steps in-process and consolidates in memory.

## Data model

```
Organisation ── threat model (Z)
System ── criticality · exposure · classification · shelf-life (X) · migration (Y)
  └─ Source ── Scan ── Occurrence (path, line, detector, rule, function, masked snippet)
  └─ Artefact (kind, identity, fingerprint, quantum/classical status) ── ArtefactLink
CbomSnapshot (CBOM, SHA-256, DSSE envelope, key id)
AuditEvent (hash-chained) · User · Session · AccessToken · Invitation
```

## Repository

```
server/falcon/
  kernel/          database, access, audit, problems, HTTP hardening, migrations runner, events
  domains/         identity, organisation, horizon, systems, discovery, risk, migration, reports, ledger, overview, platform
  discovery/       engine, catalogue, walker, workspace (acquisition), detectors, TLS probe
  risk/            facts, policies (four frameworks), model (score, Mosca, HNDL, time machine)
  migration/       recommend (PQC and hybrid), plan (waves, schedule), bench (on-host timings)
  reporting/       inventory (the report model), cbom, sarif, spdx, tabular, attest, drift
  knowledge/       versioned JSON knowledge bases and rule packs
  migrations/      Alembic revisions (0001 foundation, 0002 discovery, 0003 reports, 0004 exports)
  cli.py           offline scan, keygen, verify
  demo.py          first-run demonstration: organisation, admin account, systems, scans
  desktop.py       the engine as the desktop app runs it
server/tests/      pytest: unit tests and API tests on fresh databases built by the real migrations

console/src/
  design/          tokens, glass materials, pointer light, motion, component library
  viz/             Falcon Viz: measurement, tweening, tooltips, chart frame and the charts
  features/        auth, shell, overview, systems, horizon, discovery, risk, migration, reports, settings
  lib/             API client, queries and prefetching, formatting, desktop bridge
  app/             router, code-split pages with idle prefetch

desktop/           Tauri 2 shell (Rust), splash, PyInstaller spec for the bundled engine
fixtures/          sample estates, a container image and PKI material for tests and demos
Dockerfile, docker-compose.yml
```

## Console

- **Design.** Every surface is Apple-style glass (`glass`, `glass-strong`) over
  a soft backdrop, with light, dark and system appearances. Everything
  clickable responds to the pointer: a cursor, the pointer-following light,
  lift and press.
- **Motion.**
  - Springs drive anything the user touches.
  - Sections rise into place in sequence, animating only opacity and transform
    on the compositor.
  - Numbers count to their values.
  - All of it respects *reduce motion*.
- **Speed.**
  - Every page's code is prefetched when the console is idle.
  - Pointing at a sidebar item starts loading that page's data.
  - Filters keep the previous result on screen while the next one loads.
  - Measured: navigation paints in 32–47 ms from click, with no skeletons and
    no long tasks.
- **Feedback.**
  - A flying falcon marks loading. It is driven by React Query (first loads
    and mutations) and by the page skeleton (code), with a 280 ms show delay
    and a 900 ms minimum pass.
  - Web Audio interface sounds come from one document-level listener, so no
    component knows about them.
  - Keyboard shortcuts are one customisable registry with a single
    dispatcher.
  - A connection monitor retries and refreshes on its own.
- **Falcon Viz.** d3 supplies only the math (scales and shapes). Rendering,
  measurement, motion, interaction and accessibility are FALCON's own. Every
  chart has:
  - a validated palette;
  - reserved status colours, always with an icon and a label;
  - hover readouts;
  - a table view;
  - tweening that stays continuous when interrupted.
