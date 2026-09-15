# Pinned CI Python runtime

Vendored from forge-service commit 39556bb32a5adc65c89ab146f5a0ccf51a31e815, FS-146. Refresh the consumer, profile, lock and checksums together through PRs after source/canary review. This candidate source is not assumed merged.

The interpreter archive stays outside Git in the admitted read-only closure store. Missing or damaged snapshots fail closed. No internet download fallback, mutable current pointer, shared Python writes or pip policy relaxation. Application packages continue through the existing package mirror.
