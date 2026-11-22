# v0.1.0 research release

Status: alpha/research. This release supports reproducible inspection and
method development, not clinical interpretation. Dependency-aware unit and
synthetic integration tests accompany the source. Real-data physiological
validation is explicitly outside this release's evidence.

Publication checklist:

1. Upload only this repository directory or the release ZIP, not its parent.
2. Review the MIT license and contributor attribution for your institution's
   ownership requirements before publication; no author name or institution
   has been inferred by the packaging workflow.
3. Run tests and the supplied release scanner. Inspect the exact ZIP listing.
4. Create the GitHub repository, push the reviewed source and tag `v0.1.0`.
5. Attach the source ZIP/checksum to a GitHub release. Publishing to PyPI is
   optional and has not been performed.

The package intentionally does not ship study-specific acquisition-time tables,
raw recordings, local outputs, old caches, screenshots or access credentials.
Future versions should add independently annotated peak-detection benchmarks,
spectral validation with missing intervals, more device fixtures and explicit
modeling examples before claiming broad validity.
