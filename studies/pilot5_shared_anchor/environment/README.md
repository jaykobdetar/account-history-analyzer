# Pilot 5 preserved baseline

The [fresh verification](baseline-verification.json) passed all 17 identity checks for the unchanged AHAS 1.0.4 installation. Its 54 package files match the pinned reviewed Git tree, the reviewed source checkout and the earlier installed bytes. Configuration, resources, implementation fingerprint, interpreter and registered dependency versions remain unchanged. The fresh probe executes no corpus preprocessing, chronological analysis or production tests.

The [Pilot4 preservation manifest](pilot4-preservation-baseline.json) records byte sizes and SHA256 hashes for 301 existing Pilot4 public artifacts and ten named private source/audit/provenance inputs. Cache files are excluded. Only hashes and logical private filenames are public; this file does not export original writing or private membership. The named private list is not a complete inventory of every private Pilot4 artifact. Pilot5 adds its own records without rewriting the earlier study.

The verifier reuses the unchanged prior provenance probe and checks the actual installed files against the immutable reviewed commit `ea41d82ecc3f6585a7dc2bca92ede34740f0b62d`. The installed implementation fingerprint remains `bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179`; the analytical configuration remains `8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925`.

Actual source selection, construction and four full-history executions need their own registered inputs and receipts. Passing this identity check does not supply any chronological performance observation.
