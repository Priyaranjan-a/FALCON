# Reporting, CBOM and attestations

FALCON writes its inventory and assessment in the standard formats other tools
read, and signs snapshots of it with post-quantum cryptography. The same
writers serve three places:

- the console (**Reports**);
- the API (`/api/v1/reports/…`);
- the offline command line (`falcon scan`).

A CBOM from a CI pipeline and one from the platform therefore read alike.

| Format | Standard | Use |
|---|---|---|
| CycloneDX CBOM (JSON, XML) | OWASP CycloneDX 1.6 | The cryptography bill of materials: CBOM tools, Dependency-Track, auditors |
| SARIF | OASIS SARIF 2.1.0 | Code scanning in GitHub, GitLab, Azure DevOps and IDEs |
| SPDX | SPDX 2.3 (ISO/IEC 5962) | SBOM programmes and procurement |
| CSV | RFC 4180 | The risk register in a spreadsheet (formula injection neutralised) |
| JSON | FALCON | The complete assessment, for scripts and dashboards |

Every export is checked in the test suite. During development each one was also
validated against its official schema: the CycloneDX 1.6 JSON schema and XSD,
the OASIS SARIF 2.1.0 schema, and `spdx-tools`.

## Where exports go

Every export is written by the server and recorded in the export history, with
its size and SHA-256. Where it lands depends on how FALCON runs:

| Install | Location | In the console |
|---|---|---|
| Desktop app | A folder on the user's machine. The default is `Downloads\FALCON Exports`; **Change…** opens the native folder picker | The toast and the history offer **Show in Folder**, which selects the file in Explorer or Finder. **Open Folder** opens the folder itself |
| Server | FALCON's library, `<data>/exports`. Web users cannot change it | The browser downloads the file, and the history offers **Download again** |

A second export with the same name becomes `name (2).ext`, as in Finder and
Explorer. On a server, a stored file that has changed since FALCON wrote it is
refused rather than served. Removing an entry from the history on the desktop
leaves the user's file where it is.

The history appears in three places:

- **Reports → Exports**;
- the toolbar's downloads button (`G` then `D`);
- **Settings → Exports & downloads**.

The API is:

- `GET` and `POST /api/v1/reports/exports`;
- `GET /exports/{id}/file`;
- `POST /exports/{id}/reveal`;
- `DELETE /exports/{id}`;
- `GET`, `PUT` and `DELETE /exports/location`;
- `POST /exports/location/open`.

## CycloneDX 1.6 mapping

| FALCON artefact | CycloneDX component |
|---|---|
| Algorithm | `cryptographic-asset`, `assetType: algorithm`. `algorithmProperties` carries the primitive (the 1.6 enumeration), parameter set, curve, mode, padding, crypto functions, classical security level and NIST quantum security level (0 for quantum-vulnerable). It also carries the OID where one is registered |
| Certificate | `cryptographic-asset`, `assetType: certificate`. Carries the subject, issuer, validity, `signatureAlgorithmRef` and `subjectPublicKeyRef` (links to the algorithm and key components), and format X.509 |
| Key | `cryptographic-asset`, `assetType: related-crypto-material`. Carries public or private key, size, format, `algorithmRef` and state |
| Cloud KMS key | `related-crypto-material` (secret or private key), secured by the provider's KMS, with its algorithm |
| Protocol | `cryptographic-asset`, `assetType: protocol`. Carries the type (TLS, SSH, IPsec, IKE), the version, and the negotiated algorithms as a cipher suite |
| Library | `library`, with a package URL (`pkg:pypi/…`, `pkg:maven/…`, `pkg:npm/…`, `pkg:golang/…`) |
| Hardware module | `device`, with its supplier |
| System | `application`; `dependencies` link each system to the cryptography found in it |

**Evidence.** Each component carries `evidence.occurrences`: file, line,
column, and the detector and rule that found it. `evidence.identity` names the
analysis technique, for example source-code analysis, AST fingerprint, binary
analysis, manifest analysis or dynamic analysis for live TLS.

**Assessment.** FALCON's analysis travels as `falcon:*` properties:

- quantum and classical status;
- risk score and band;
- Mosca X, Y and Z and the CRQC probability;
- HNDL exposure;
- per-framework compliance;
- the recommended replacement and its hybrid.

**Stable references.** `bom-ref` is `crypto/<system code>/<fingerprint>`. The
fingerprint is derived from what the artefact *is*, so the same certificate or
algorithm keeps its reference across scans and exports. This is what makes
drift computable.

## SARIF rules

| Rule | Name | Default level |
|---|---|---|
| FALCON001 | Broken or weak cryptography | error |
| FALCON002 | Harvest now, decrypt later exposure | error |
| FALCON003 | Quantum-vulnerable key establishment | warning |
| FALCON004 | Quantum-vulnerable signature or certificate | warning |
| FALCON005 | Symmetric strength halved by Grover's algorithm | note |
| FALCON006 | Library at end of life or without a post-quantum path | warning |
| FALCON007 | Disallowed by a compliance framework | error |
| FALCON008 | Expired certificate | warning |

There is one result per rule, artefact and line of code, up to ten locations per
artefact. The level follows the artefact's risk band: critical and high are
errors, medium is a warning, low is a note. `security-severity` is the risk score
over ten, which GitHub uses to rank alerts. Evidence from live TLS endpoints has
no file, so it is reported as a logical location. Stable
`partialFingerprints` let code-scanning services track an alert across commits.

## Signed snapshots (attestations)

A snapshot fixes the inventory at a moment as evidence: for an audit, a board
report, or a baseline to measure migration against.

1. FALCON writes the CBOM and computes the SHA-256 of its canonical form (sorted
   keys, no whitespace). The serial number and timestamp are left out of the
   hash, so the digest identifies the content.
2. It wraps the CBOM in an **in-toto Statement v1**: the subject is the digest,
   and the predicate type is `https://cyclonedx.org/bom/v1.6`.
3. It signs the **DSSE** pre-authentication encoding with the organisation's
   **ML-DSA-65** key (FIPS 204, NIST security category 3):

       PAE = "DSSEv1" SP len(type) SP type SP len(body) SP body

   The public key is 1,952 bytes and the signature 3,309 bytes.

The key lives in the data directory (`keys/`, mode 0600 on POSIX). Rotating it
(owners and administrators) keeps the previous public keys, so older snapshots
stay verifiable. Signing needs the `reports.sign` permission (owner,
administrator, security lead). Every signature, export and rotation is
recorded in the audit ledger.

**Verification** has four checks:

1. The envelope is well formed.
2. The ML-DSA-65 signature holds under a known key.
3. The payload is an in-toto statement with a CycloneDX predicate.
4. The CBOM inside matches the signed digest.

For stored snapshots FALCON also checks that the database copy matches what
was signed.

Verification is available in three places:

- the console: select a snapshot, or drop any `.dsse.json` file on *Verify an
  attestation*;
- the API: `POST /api/v1/reports/verify`;
- the command line: `falcon verify cbom.dsse.json --key falcon-attestation.pub.pem`.

It also works with **OpenSSL 3.5 or later**, without FALCON:

```sh
# payload and signature out of the envelope (jq and base64)
jq -r .payload cbom.dsse.json | base64 -d > body.json
jq -r '.signatures[0].sig' cbom.dsse.json | base64 -d > signature.bin
# rebuild the DSSE pre-authentication encoding
TYPE=application/vnd.in-toto+json
printf 'DSSEv1 %d %s %d ' ${#TYPE} "$TYPE" $(stat -c %s body.json) > pae.bin && cat body.json >> pae.bin
openssl pkeyutl -verify -pubin -inkey falcon-attestation.pub.pem -rawin -in pae.bin -sigfile signature.bin
# Signature Verified Successfully
```

## Drift

Drift compares two CBOMs by `bom-ref`. The CBOMs can be two snapshots, a
snapshot and the current inventory, or any two CycloneDX files FALCON wrote.
It reports:

- what was **retired**, **introduced** and **changed** (quantum status, risk
  band, score, HNDL, number of occurrences);
- the direction of each change;
- totals before and after (risk points, quantum-vulnerable and post-quantum
  assets);
- a verdict: improved, regressed, mixed, changed or unchanged.

This is how a migration is verified against signed evidence rather than claimed.

## Executive brief

**Reporting → Executive Brief** is a one-document summary for a board, a
ministry or an auditor. It covers:

- the headline position;
- the risk profile;
- the systems most at risk;
- compliance against each framework;
- the migration roadmap and its replacements;
- the assets to act on first;
- the latest signed snapshot as evidence.

**Print or save PDF** produces an A4 document in light appearance with the
status colours intact.
