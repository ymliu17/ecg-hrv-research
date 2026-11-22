# Synthetic example expectations

All included/example-generated signal values are simulated. No real waveform
or participant identifier is used. IDs beginning `synthetic-` identify generated
examples, not anonymized participants.

- Included `synthetic_smoke`: 60 s, 250 Hz, seed 2026, two opposite-polarity leads.
- Default generator: 360 s, 250 Hz, same deterministic seed.
- Lab run: one output row, all 18 HRV columns present; MeanHR roughly 60–85 bpm.
  The 60-s example has blank frequency results under the default policy.
- MRI windows on the longer example: nine rows with starts 0, 30, …, 240 and
  ends 60, 90, …, 300; all `FullWindow=True`, `OverlapFraction=0.5`.
- QC yield and exact numerical values are not frozen across library/platform
  combinations. See `provenance.json` for the versions used in a particular run.
- Generator reference R centers are stored separately, allowing later detector
  validation. CLI integration tests currently check expected behavior, not a
  claimed clinical sensitivity/specificity score.

Regenerate the included data with:

```sh
ecg-hrv synthetic --output examples/synthetic_smoke_new --duration 60 --sampling-rate 250 --seed 2026
```

Generated directories must not already exist. Never replace the example files
with actual participant recordings when preparing a release.
