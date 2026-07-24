# Evidence Bundles

Evidence bundles are local packets for AI-assisted proposal drafting. They may
include raw excerpts from private sessions, repos, or client code, so generated
bundle JSON and prompt files are ignored by Git by default.

Generate one with:

```powershell
python .\tools\agent_archive.py baseline bundle --focus my-project
```
