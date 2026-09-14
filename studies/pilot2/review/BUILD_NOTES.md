# Review-only build corrections

The first final-review render failed before creating its summary: the report builder treated the prepared plan's integer `final_source_accounts` as a list. The executed builder and raw failure are retained under `logs/final-review-render.*`. The builder now consumes the documented integer directly; final review checks compare it with the actual plan. No measurement, input, frozen driver or outcome was changed.

An interactive post-replay assertion also initially expected the native verification status spelling `verified`. The actual successful command returned `reproduced`, with all fourteen canonical artifact names. The corrected review-only checker asserts that exact native contract, its complete scope and five SVG artifacts. This was a checker expectation error, not a failed numerical replay. The actual replay command exited zero and its original stdout/receipt remain unchanged.
