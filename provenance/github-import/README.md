# Fresh GitHub import checks

These receipts were executed against this imported 1.0.4 checkout on 2026-09-14. They are separate from the earlier component tests, audit regressions and container receipts.

The import check compared 634 frozen release files (all copied files except the documented README/.gitignore navigation changes) and all 317 original sanitized pilot files. The implementation and analytical configuration hashes match the frozen 1.0.4 baseline. A fresh arithmetic CLI analysis and full canonical replay ran with internet sockets denied; the replay returned `reproduced` for all fourteen canonical artifacts. Its original stdout records the exact scope and hashes.

The staged audit and publication file manifest cover the additional documentation and exact Git content. Raw corpora, private prose/maps and credentials are not part of this source/documentation import. The bundled pattern check is a narrow credential-format check, not a broad security-audit claim.
