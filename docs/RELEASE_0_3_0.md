# 0.3.0 release readiness

Release preparation is separate from publication. The owner requested release
on 2026-09-15; the final release-preparation PR still requires merge before
tagging. A dated changelog is not proof that PyPI publication succeeded.

Before the owner chooses to release:

- Merge the reviewed onboarding and collection-health PRs intended for this release.
- Require real Linux and native-Windows test results, including
  `tests/test_installed_wheel.py`, on the final release commit.
- Run `python -m build` and `python -m twine check dist/*`; verify the wheel contains
  `agent_sessions/default_sources.toml` and its installed version is 0.3.0.
- Confirm the router's setup instructions and collection-health commands match its
  separately approved Marketplace version. The hub remains compatible with router 0.2.1.
- Change the candidate heading in CHANGELOG to the actual release date through a PR.
- Only after explicit owner release approval, tag the approved commit `v0.3.0` using
  the existing release workflow. Website and Marketplace publication are separate
  owner-approved actions, not consequences of opening these PRs.

The tag-triggered build and PyPI publication run on GitHub only: the publisher
uses GitHub OIDC, not a Forgejo job identity. Install all build tooling inside
the private venv. Sync the exact reviewed main commit to GitHub before tagging;
do not push unreviewed work or private archives. Confirm the tag does not already
exist and require its commit to match the validated release head.

After the release workflow succeeds, verify the `agent-session-hub` 0.3.0 PyPI
metadata and install its wheel in a fresh private workspace. Exercise `--version`,
`init`, and the synthetic router journey. Create GitHub release notes from that
same tag only; distinguish GitHub source publication from PyPI availability.

Validation failure or a fresh-install/router handoff regression blocks publication.
If found after publication, keep local archives intact and ship a reviewed patch;
do not uninstall or overwrite user archives. The prior 0.2.0 package requires a
configured source checkout and is not a substitute for repo-free onboarding.
