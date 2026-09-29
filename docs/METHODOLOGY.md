# Risk methodology

How FALCON turns a discovered cryptographic artefact into a risk score, a
classification, a compliance position and a migration wave. Every weight below
lives in `server/falcon/knowledge/risk.json` (version 2026.09). An organisation
can review the weights there; the code reads them, it does not repeat them.

## 1. The threat horizon (Mosca's Z)

The time until a cryptographically relevant quantum computer (CRQC) exists,
*T* years from now, is modelled as log-normal with median *m* and shape σ:

    P(T ≤ t) = Φ((ln t − ln m) / σ)

| Scenario | Median CRQC year | σ |
|---|---|---|
| Aggressive | 2031 | 0.45 |
| Moderate | 2036 | 0.40 |
| Conservative | 2042 | 0.35 |
| Custom | chosen by the organisation | from its uncertainty setting |

The organisation chooses a **tolerance** *q*: the chance of arrival it will accept
before it has migrated. The planning horizon is the *q*-quantile:

    Z = exp(ln m + σ · Φ⁻¹(q))

With a 5% tolerance, the organisation plans as though a CRQC arrives at the point
where there is a 1-in-20 chance it already exists. The scenarios are planning
assumptions, not forecasts. They should be calibrated against the threat
intelligence the organisation relies on.

## 2. Mosca per artefact (X and Y)

Mosca's inequality says the protected data is exposed when **X + Y > Z**. FALCON
evaluates it for every artefact, not only for every system.

**X: how long what the artefact protects must stay protected.** It depends on
the artefact's role (section 3):

- Confidentiality (key establishment, encryption), and the libraries and
  hardware that provide it: the system's **data shelf-life**. Traffic recorded
  today can be decrypted later.
- Certificates: the **remaining validity**, capped at 50 years. Self-signed
  test certificates can claim centuries.
- Other signatures: **0**. A forgery cannot reach back in time; signatures are
  exposed only once a CRQC exists.

**Y: how long replacing the artefact takes.** It is estimated from what the
artefact is and where it was found:

| Evidence | Y (years) |
|---|---|
| Algorithm set in configuration | 0.25 |
| Protocol version or group | 0.5 |
| Leaf certificate | 0.5 |
| Key | 0.5 |
| Library with a post-quantum release | 0.5 |
| Cloud KMS key | 0.75 |
| Algorithm in source code | 1.0 |
| Algorithm in a compiled binary | 1.5 |
| Library with no post-quantum path | 1.5 |
| Certificate authority (PKI hierarchy) | 3.0 |
| Hardware module | 3.0 |

A system's own **estimated Y** is refined from discovery. It is the longest
artefact migration plus coordination time that grows with the number of
affected artefacts:

    Y_system = max(Yᵢ) + 0.15 · log₂(1 + n)

FALCON reports three things per artefact:

- **Exposure years** X + Y − Z. Positive means exposed; between −2 and 0 is
  *watch*.
- The probabilistic form **P(T ≤ X + Y)**.
- The latest **start-by** date, now + Z − X − Y.

## 3. Roles

An artefact's role is derived from its kind, its primitive and how the code
uses it, which the detectors record as the function at each occurrence:

| Role | Examples |
|---|---|
| Confidentiality | key agreement, KEM, public-key encryption, symmetric ciphers, TLS, SSH and IPsec, RSA key transport |
| Authenticity | signatures, certificates, keys used for signing |
| Integrity | hashes, MACs, KDFs, random generation |
| Enabling | libraries and hardware modules |

RSA is authenticity-only unless it is used to encrypt or transport keys, as in
RSA key exchange in TLS, RSA-OAEP or PKCS #1 v1.5 encryption.

## 4. Score

    score = round(100 × impact × likelihood)        (0–100)

**Impact** is what the system is worth. Classification applies only to
confidentiality artefacts:

    impact = criticality × exposure × classification

| Factor | Values |
|---|---|
| Criticality | critical 1.0 · high 0.8 · moderate 0.55 · low 0.3 |
| Exposure | external 1.0 · partner 0.9 · internal 0.75 · isolated 0.55 |
| Classification | secret 1.0 · restricted 0.9 · confidential 0.75 · internal 0.55 · public 0.35 |

**Likelihood** is the largest of three independent reasons to act. The one
that wins is reported as the **driver**.

- **Classical**, attackable today: broken 1.0, weak 0.75, legacy 0.4.
  - Libraries: end of life 0.6, abandoned 0.5.
- **Quantum:** severity × P(T ≤ X + Y).
  - Severity: vulnerable 1.0, weakened (Grover) 0.3, unknown 0.2, hybrid,
    resistant and PQC 0.
  - Hardware: 0.35.
  - Libraries: no post-quantum path 0.45, unknown 0.2.
- **Policy**, deadline pressure:
  - 1.0 once a NIST disallowance has passed.
  - Otherwise, a logistic curve on the slack between the deadline and the
    migration time:

        pressure = 1 / (1 + exp((deadline − now − Y − 2.5) / 1.1))

    Pressure is ½ when the migration must start within 2.5 years to meet the
    deadline, and approaches 1 when it can no longer be met.
  - An artefact that is already deprecated but still permitted is floored
    at 0.5.

**Bands:** critical ≥ 60, high ≥ 35, medium ≥ 15, low ≥ 1, otherwise *no
quantum risk*.

Every score is explained. The console and the exports list the drivers, for
example "63% chance a CRQC exists within X + Y = 13.0 years" or "NIST deadline
at the end of 2030, 4.3 years away; migrating it takes 1.5 years".

## 5. Harvest now, decrypt later (HNDL)

An artefact is **harvestable** when all three hold:

- it provides confidentiality;
- it is quantum-vulnerable;
- it is not a library or a hardware module.

Its **reach** is where an adversary can record the traffic:

| System exposure | Reach |
|---|---|
| external | internet |
| partner | partner networks |
| internal | insiders |
| isolated | none |

It is **exposed** when it is harvestable, it has some reach, and its Mosca
exposure is positive. An exposed artefact on an internet- or partner-facing
system is never rated below **high**, whatever its score, because the recorded
traffic already outlives the horizon.

## 6. Classification

Each artefact is classified along the four axes the problem statement names:

- **Type:** algorithm, key, certificate, protocol, library, hardware or cloud
  service.
- **Lifetime:** X banded as under 1 year, 1–5, 5–10, 10–25 or 25 years and
  more.
- **Criticality:** the owning system's criticality.
- **Mosca state:** exposed, watch, clear or not affected.

The Quantum Risk page shows the type × lifetime matrix and the likelihood ×
impact matrix.

## 7. Compliance

Four frameworks are evaluated per artefact, with their published dates. "After
2030" takes effect on 1 January 2031.

| Framework | Rule applied |
|---|---|
| NIST IR 8547 (draft) | Quantum-vulnerable public-key cryptography at 112-bit security deprecated after 2030; all quantum-vulnerable public-key cryptography disallowed after 2035 |
| NIST SP 800-131A Rev. 2 | Below 112-bit security disallowed. TDEA disallowed after 2023. SHA-1 disallowed for signature generation, deprecated elsewhere until 2030 |
| CNSA 2.0 (NSA) | Approved: AES-256, SHA-384/512, ML-KEM-1024, ML-DSA-87, LMS/XMSS, HMAC with SHA-384/512. Anything else must transition, with exclusive use required from 2030 to 2033 depending on the kind of system |
| EU PQC roadmap | Quantum-vulnerable public-key cryptography must transition: high-risk use cases by the end of 2030, the rest by the end of 2035 |

Each result is one of: approved, acceptable, must transition, not approved,
deprecated, disallowed or not applicable. Each carries the rule that produced
it. Check the rules against the current text of each publication; NIST IR 8547
is a draft.

## 8. Time machine

Each artefact carries the years its state changes, so the console can replay
any year without asking the server:

- **At risk:** from today, if it is quantum-vulnerable, weakened, unknown or
  classically weak.
- **Exposed:** Z − X for confidentiality, or Z − Y for authenticity.
- **Broken:** the earliest of the policy disallowance, the planning horizon,
  or today if it is already classically broken.

## 9. Recommendations and waves

The recommendation engine (`knowledge/pqc.json`) proposes a primary
replacement, a hybrid for the transition, and alternatives. It also gives the
overhead on the wire (FIPS 203/204/205 sizes) and the latency measured on the
host by the benchmark lab.

**Category 5 algorithms** (ML-KEM-1024, ML-DSA-87, P-384 hybrids) are chosen
when the system's data is *secret* or *restricted*, or the system is
*critical*. Otherwise category 3 (ML-KEM-768, ML-DSA-65, X25519MLKEM768).

Every artefact that needs action joins the first wave that matches:

1. **Fix now:** classically broken or weak, or already disallowed.
2. **Stop the harvest:** HNDL-exposed, plus the library upgrades those systems
   depend on.
3. **Long lead:** Y ≥ 1.5 years, hardware, cloud keys, certificate authorities.
4. **Before 2030:** critical or high risk, or a NIST deadline at the end of 2030.
5. **Complete:** everything else quantum-vulnerable or weakened.

A wave lasts as long as its longest item, plus 0.1 · log₂(1 + n) years of
coordination. It is on time when it finishes before its deadline. The plan
reports the completion date and the chance a CRQC exists by then.
