# Changelog

## 0.1.0 — 2026-11-21

Initial research release: installable package, a single CLI, validated JSON
configuration, explicit recording manifests, lab/GE MRI/BIOPAC MRI profiles,
18 HRV fields, timestamp-preserving RR handling, optional Malik sensitivity
comparison, target-specific QC, 60-s windows with 50% overlap, deterministic
synthetic examples, tests, CI definition and input/dependency provenance.

Known limitations: no physiological validation, no universal MRI artifact
suppression, no automatic study segmentation or lead ranking, and conservative
frequency duration gating. Compatibility with historical study tables is not
promised. No actual participant data or study caches are shipped.
