# Contributing

Install `.[dev]`, run `python -m pytest -q`, and include synthetic regression
cases with changes. Preserve original timing and do not introduce hidden
cross-file concatenation, cache reuse or automatic synchronization assumptions.
New QC presets require a documented purpose and explicit configuration values.

Do not submit participant data, identifiers, acquisition logs, local absolute
paths or institutional credentials in examples, issues or test fixtures. Use
synthetic inputs and describe the dependency versions and failing behavior.

Before proposing a scientific accuracy claim, distinguish software regression
tests from physiological validation against independent expert annotations.
