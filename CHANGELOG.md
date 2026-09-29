# Changelog

All notable changes to FALCON are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-09-29

The first complete release, delivered in five phases for Smart India Hackathon
problem statement 26164.

### Discovery

- Seven artefact classes catalogued: algorithms, keys, certificates,
  protocols, libraries, hardware modules and cloud key services.
- Sources: folders, archives, Git repositories, container images (saved
  tarballs, OCI layouts and registry pulls) and live TLS endpoints.
- Detectors: a Python syntax-tree analyser, 259 rules across 11 language
  packs, dependency manifests and lockfiles, ELF/PE/Mach-O binaries, Java
  bytecode, certificates and keystores, TLS/SSH/IPsec configuration, and
  infrastructure-as-code KMS keys and HSMs.
- A post-quantum TLS 1.3 probe offering X25519MLKEM768 with a real ML-KEM-768
  key share.
- Scans run in isolated worker processes with live progress over
  Server-Sent Events, and a coverage treemap.
- Artefacts are de-duplicated by a stable fingerprint, keeping their identity
  and history across scans.

### Risk

- Mosca's inequality per artefact: X from the artefact's role, Y from where it
  was found, Z from a log-normal CRQC arrival model.
- Score = impact × the strongest of classical attack, P(CRQC within X + Y) and
  policy deadline pressure, with every driver explained.
- Harvest-now-decrypt-later exposure by role and reach.
- Classification by type, lifetime, criticality and Mosca state.
- Compliance with NIST IR 8547, NIST SP 800-131A, CNSA 2.0 and the EU PQC
  roadmap.
- The Quantum Time Machine replays the estate year by year to 2045.

### Migration

- Recommendations with a primary post-quantum replacement, a hybrid for the
  transition and alternatives, carrying FIPS 203/204/205 sizes.
- A benchmark lab timing ML-KEM, ML-DSA, hybrid and classical algorithms on
  the host.
- Five migration waves scheduled per system on a roadmap.
- A blast-radius graph of shared cryptography, and a what-if simulator.
- Scan-to-scan verification of what was retired, introduced or spread.

### Reporting

- CycloneDX 1.6 CBOM in JSON and XML, SARIF 2.1.0, SPDX 2.3, CSV and JSON,
  each validated against its official schema.
- CBOM snapshots signed with ML-DSA-65 (FIPS 204) in a DSSE envelope carrying
  an in-toto Statement v1, verifiable with OpenSSL 3.5.
- Drift between snapshots, or against the live inventory.
- An export library with history, and a printable executive brief.

### Platform

- A web console with light, dark and phone layouts, a command palette,
  rebindable keyboard shortcuts, interface sounds and a flying-falcon loading
  indicator.
- A Windows desktop app (Tauri 2) with the engine bundled.
- A Docker image running as a non-root user on a read-only root file system.
- An offline command line (`falcon scan`, `keygen`, `verify`) for CI, with
  `--fail-on` gating.
- Identity and access with six roles and explicit permissions, Argon2id
  passwords, lockout and rate limits.
- A SHA-256 hash-chained audit ledger that detects alteration, deletion,
  reordering and truncation.
- A first-run demonstration that seeds an organisation, systems and real scans
  so a fresh installation opens as a working platform.

### Verified

- 326 server tests, run on Windows and Linux; API tests build their database
  from the real migrations.
- Exports validated against the CycloneDX 1.6 schema and XSD, the OASIS SARIF
  2.1.0 schema and `spdx-tools`.
- ML-DSA signatures cross-checked with stock OpenSSL 3.5 in a clean container.

[1.0.0]: https://github.com/shriomverma100/FALCON/releases/tag/v1.0.0
