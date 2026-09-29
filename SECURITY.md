# Security

## Reporting a vulnerability

Please report security issues privately: open a
[private vulnerability report](https://github.com/shriomverma100/FALCON/security/advisories/new)
on this repository rather than a public issue. Include the steps to reproduce,
the affected version, and the impact you expect. You will get an acknowledgement
within three working days.

## Security model in brief

- **Identity:**
  - Argon2id password hashing, account lockout and per-address rate limits.
  - Server-side sessions in `HttpOnly`, `SameSite=Strict` cookies, plus a
    request header check against cross-site request forgery.
  - Personal access tokens are stored as hashes.
- **Authorisation:** six roles map to explicit permissions, and every API
  endpoint checks a permission.
- **Audit:** every change, export, signature and key rotation is recorded in a
  SHA-256 hash-chained ledger that can be re-verified from the console.
- **Scanning:**
  - Each scan runs in its own process with time and size limits.
  - Archives are checked for path traversal and archive bombs, and symbolic
    links are ignored.
  - Git hooks, submodules and credential helpers are disabled.
  - Secrets found in code are masked before findings leave the worker, and
    private-key material is never stored.
- **Transport and browser:** a strict Content Security Policy, frame denial,
  `X-Content-Type-Options` and `Referrer-Policy`. Behind a TLS proxy,
  production cookies are `Secure`.
- **Evidence:** CBOM snapshots are signed with ML-DSA-65 (FIPS 204) and are
  verifiable with OpenSSL 3.5.

## The demonstration account

`falcon serve --demo`, run by `scripts/start` and `docker compose`, creates the
account `admin@falcon.local` with a published password, **for evaluation
only**. Change the password after signing in, or set your own before the first
start with `FALCON_DEMO_ADMIN_EMAIL` and `FALCON_DEMO_ADMIN_PASSWORD`. For a
production installation, start without the demo (`start.ps1 -NoDemo`,
`start.sh --no-demo`, or `falcon serve`) and use the setup assistant.

The full posture is described in [docs/OPERATIONS.md](docs/OPERATIONS.md#security-posture).
