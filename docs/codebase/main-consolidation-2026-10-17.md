# Main branch consolidation — 2026-10-17

Author: Brent Thompson <brent.thompson@ucf.edu>

This consolidation preserves the existing GitHub main merge and brings the remaining reviewed
Slurm metrics, output synchronization, exact concept lineage and extraction quarantine work into main.
The combined workflow revision is `2026-10-17-lineage-quality`; the newer embedding-based parent
selection remains enabled. Normalization now saves eight returned products including exact lineage.

## Preserved inputs

| Work | Preserved commit |
|---|---|
| GitHub main before consolidation | `38702c9` |
| Slurm metrics and output synchronization | `bf3c210` |
| Pending concept-lineage worktree | `16df011` |
| Pending extraction-quality worktree | `f53e494` |
| Unfinished incremental sweep | `030a8a4`, retained by `archive/sweep-wip-2026-10-17` |

The unfinished sweep commit explicitly lacks CLI wiring, incremental integration, reporting and tests.
It is archived as approved; its dormant implementation is not part of the consolidated runtime.
Historical merged branch names can be removed because their commits remain ancestors of main.

Before committing or merging, local Git bundles, binary patches, untracked source files and all ignored
worktree files were copied into `outputs/development/main-consolidation-20261017/`. SHA256 fingerprints
are recorded in `files.json`; `refs-before.json` preserves the original branch tips. These local recovery
files are ignored by Git. Worktrees are archived only after their commits are present in main and their
ignored files have been preserved. Shared stores, runtime dependencies and scientific results are not
rewritten by consolidation.

## Compatibility and verification

- The lineage and quarantine branches retain their original commits through normal merges.
- Original member labels remain available through enrichment and OWL export; malformed concepts and
  dependent links remain in review artifacts and do not enter normalization.
- A combined fixture checks quarantine and exact lineage together. Legacy n15 links remain reconstructed
  because their saved runs predate the lineage sidecar; no original run is backfilled.
- Agent recipes and data-flow documentation describe recorded lineage for new runs and preserve
  legacy checks for older outputs. The normalization recipe includes the identity-recording operation.
- Pipeline suite: **196 passed**, including real Bash fixtures with fake GPU/CLI commands.
- Dashboard/documentation suite: **73 passed**. Saved-model inheritance is isolated from whether a
  local Ollama service happens to be running. The cancellation fixture stops only its own child process.
- Initial restricted-process failures concerned Windows temporary files, locks and cancellation.
  Host-permission runs with workspace-local temporary storage passed. RDFLib deprecation warnings remain.

The current ontology validation details are in [validation.json](../ontology/validation.json).
No live model, GPU allocation or Slurm job was launched by these checks.
