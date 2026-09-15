# AHIF contract adoption and companion bridge

The reviewed AHIF **0.1.1** destination format is adopted separately from the
frozen AHAS **1.0.4** engine and **1.0.0** production input schemas.

## Pinned companion implementation

- Repository: [jaykobdetar/ahif](https://github.com/jaykobdetar/ahif)
- Reviewed companion commit: [`3822a21f09ca9b9c9766a281a7489db8a325b04d`](https://github.com/jaykobdetar/ahif/commit/3822a21f09ca9b9c9766a281a7489db8a325b04d)
- [Supported boundaries and CLI](https://github.com/jaykobdetar/ahif/blob/3822a21f09ca9b9c9766a281a7489db8a325b04d/docs/BRIDGE.md)
- [Source profile 1.0.0](https://github.com/jaykobdetar/ahif/blob/3822a21f09ca9b9c9766a281a7489db8a325b04d/profiles/reddit-export-csv/1.0.0/README.md)
- [Conservative projection 1.0.0](https://github.com/jaykobdetar/ahif/blob/3822a21f09ca9b9c9766a281a7489db8a325b04d/profiles/ahas-conservative/1.0.0/README.md)
- [Projection receipt schema](https://github.com/jaykobdetar/ahif/blob/3822a21f09ca9b9c9766a281a7489db8a325b04d/profiles/ahas-conservative/1.0.0/receipt.schema.json)
- [Actual integration report](https://github.com/jaykobdetar/ahif/blob/3822a21f09ca9b9c9766a281a7489db8a325b04d/docs/BRIDGE_REPORT.md)
- [Sanitized integration summary](https://github.com/jaykobdetar/ahif/blob/3822a21f09ca9b9c9766a281a7489db8a325b04d/qa/bridge/private-integration-summary.json)

The normalizer and projection live in the companion repository. This repository
adds documentation and a verbatim 92-file format/history copy; it does not add an
engine dependency, alter schemas/defaults or rebuild the frozen release.

## Preservation and new verification

[Contract inventory](contract-inventory.json) records the SHA-256 of every copied
file under `docs/ahif/`. The historical 0.1.0 package and 0.1.1 schemas, examples,
checks and receipts remain unchanged. Git attributes preserve these bytes across
checkout line-ending settings.

[Fresh verification](verification.json) and [test log](format-tests.log) record
all **61** format tests passing in the existing AHAS environment, including actual
production-schema rejection of direct AHIF input, with **zero skips**. The companion
publication check separately passed **39** bridge tests. All 70 checked engine,
configuration, schema and resource files match analyzer baseline
`6f465bd95fa3c12df41235986a96a04cf6c332d0`.

The earlier adoption/package receipts retain their original outcomes and layouts.
In particular, their 60-pass/one-skip standalone result is not overwritten by this
61-pass analyzer-checkout run. No private account source or report was read or
reanalyzed for this repository update. No prior study or release artifact changed.
