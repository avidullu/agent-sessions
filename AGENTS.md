# Agent Working Agreement

## Default delivery workflow: PR -> review -> resolve -> merge

For normal project work, operate in small, reviewable pull requests:

1. Start from the remote base branch, not the current local branch.
2. Implement one coherent tracker row, bug fix, or reviewable slice per PR.
3. Push the branch and open a PR for review.
4. Wait for review comments or an explicit LGTM before merging.
5. Address review comments in the same PR, rerun relevant checks, and wait for LGTM again.
6. Merge only after the PR has LGTM or explicit owner approval scoped to that PR.
7. After merge, refresh from the remote base branch before starting the next slice.

Do not batch a whole project into one implementation PR unless the owner explicitly asks for it.
Do not continue building later tracker rows on top of an unreviewed PR as though it is already merged.

## Exception: broad exploration branches

A temporary broad branch is acceptable only when the work is time-critical,
convoluted, or hairy enough that the boundaries are not yet knowable. Treat that
branch as exploration, not the deliverable.

Before shipping, split the result back into reviewable PRs whenever practical.
If splitting is not practical, say why in the PR description and call out the
larger review burden clearly.

## Review response discipline

When a PR receives comments, resolve them before merge:

- inspect every comment and requested change;
- make the smallest fix that addresses the concern;
- reply or summarize what changed;
- rerun the relevant checks;
- wait for LGTM before merging.

If a tool cannot formally approve because the PR author and reviewer are the same
GitHub account, require an explicit owner LGTM comment or instruction before merge.
