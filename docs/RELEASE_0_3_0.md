# 0.3.0 release readiness

This PR prepares the package; it does not publish or authorize a release.

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

Validation failure or a fresh-install/router handoff regression blocks publication.
If found after publication, keep local archives intact and ship a reviewed patch;
do not uninstall or overwrite user archives. The prior 0.2.0 package requires a
configured source checkout and is not a substitute for repo-free onboarding.
