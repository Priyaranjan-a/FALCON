<!-- Thank you for contributing to FALCON. -->

## What does this change?

<!-- A sentence or two. If it closes an issue, write "Closes #123". -->

## Why?

<!-- The problem this solves. Reviewers need the reasoning, not just the diff. -->

## How was it verified?

<!-- Name the tests you added or ran. For a bug fix, confirm the new test fails without the change. -->

- [ ] `cd server && .venv/bin/python -m pytest` passes
- [ ] `cd console && npx tsc -b && npx vitest run && npm run build` passes
- [ ] A test covers this change (and fails without it, for a bug fix)
- [ ] Documentation updated (README and `docs/`) if behaviour changed
- [ ] No real keys, certificates or private data added to the repository
