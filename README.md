# ECG HRV Research — v0.1.0

An auditable Python research pipeline for ECG-derived heart rate and HRV. One
command handles lab/session/assessment signals, whole-recording MRI ECG and
60-second MRI sliding windows. **Alpha research software, not a clinical device
or a validated general-purpose MRI artifact-removal method.**

Only code, configurations, tests and explicitly synthetic examples are included.
No participant recordings, participant metadata, original study CSVs or caches
are distributed. This repository does not require the original study workspace.

## Install

Python 3.11 or newer:

```sh
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
ecg-hrv --version
```

For BIOPAC `.acq` input: `python -m pip install -e '.[biopac]'`.
`requirements-tested.txt` pins direct numerical dependencies from the tested
environment; it is not a full transitive lockfile.
`requirements-py311-tested.lock` records the complete locally tested runtime/test
environment on Python 3.11/macOS (not a hash-verified cross-platform lock). Broad dependency ranges in
`pyproject.toml` permit installation on other platforms but do not imply those
combinations have all been validated.

## Quick start: synthetic only

From the repository root:

```sh
# Included 60-s example (no physiological source data)
ecg-hrv run --config configs/lab.json \
  --manifest examples/synthetic_smoke/manifest.json --output outputs/smoke

# Generate a longer deterministic example for lab and MRI window demonstrations
ecg-hrv synthetic --output examples/generated --duration 360 --sampling-rate 250 --seed 2026

ecg-hrv run --config configs/lab.json \
  --manifest examples/generated/manifest.json --output outputs/lab

ecg-hrv run --config configs/mri_ge_windows.json \
  --manifest examples/generated/manifest.json --output outputs/mri-windows
```

The synthetic waveform contains analytic P/QRS/T components, modulation and
noise; it does **not** reproduce MRI gradient artifacts or clinical arrhythmias.
`reference_peaks.csv` records the generator's known R-wave centers. It is not a
manual annotation of clinical recordings. See [example expectations](examples/EXPECTED.md).

Output directories must not already exist. Choose a new name for each run.
Exit status is `0` for completed runs (including QC failures), `2` for configuration
errors or at least one recording-level processing error. Error records remain in
`metrics.csv`; non-error records can still be used after checking their QC.

## Configurations

| Configuration | Detector | Analysis | Companion lead |
|---|---|---|---|
| `lab.json` | NeuroKit cleaning, polarity handling, peak correction; explicit fallback | Whole supplied segment | Optional |
| `mri_ge_whole.json` | 5–20 Hz bandpass, polarity, NeuroKit peaks | First 300 s | Required for QC |
| `mri_biopac_whole.json` | 5–40 Hz bandpass, amplitude threshold, 0.5-s minimum peak spacing | First 300 s | Optional |
| `mri_ge_windows.json` | Same GE detector, once per analysis segment | First 300 s, 60 s windows / 30 s step | Required for QC |
| `mri_biopac_windows.json` | Same BIOPAC detector | First 300 s, 60 s windows / 30 s step | Optional |

These are explicit research presets, not universal clinical thresholds. Session
and assessment use the same `lab` profile; their experiment labels belong in the
user's manifest and downstream analysis. All configuration keys and QC settings
are validated. See [methods](docs/METHODS.md) for equations and thresholds.

For 300 s, the sliding grid contains **9 windows**: 0–60, 30–90, …, 240–300 s.
Incomplete/empty positions in a requested grid remain present but unusable.
Windows are measured in **seconds**, not 20-TR patches. Align fMRI features to the
same intervals. Overlapping rows are not independent samples; split modeling
by participant and account for repeated observations in downstream analyses.
The package does not fit models or perform cross-validation.

## Input manifest

```json
{
  "recordings": [
    {
      "id": "example-run-001",
      "file": "recording.csv",
      "second_file": "companion.csv",
      "format": "csv",
      "column": "ecg",
      "time_column": "time_s",
      "sampling_rate_hz": 1000,
      "start_s": 0,
      "duration_s": 300
    }
  ]
}
```

Files resolve relative to the manifest, not the working directory. IDs must be
unique; use nonidentifying IDs. `second_file`, time selection and `time_column`
are optional. Both leads use the same format/channel settings and must have the
same sample rate and source clock. `start_s` is the explicit source-recording
analysis offset; the package never guesses synchronization from names or mtime.
It never auto-concatenates files. Export verified continuous segments before
processing them. When a companion is missing/unusable and required, QC fails;
the main lead is still processed when possible.

Supported loaders:

- **csv**: headered numeric ECG column, optional time column (seconds).
- **ge**: headerless, one numeric ECG sample per line; configure sample rate.
- **mwi**: sample-rate header, time column and signal columns; literal escaped
  tabs/newlines are supported. The file header determines sample rate.
- **opensignals**: comment-prefixed metadata and whitespace-separated samples;
  specify the zero-based ECG column and sample rate explicitly.
- **acq**: optional `bioread` loader; specify zero-based channel index. The file
  determines sample rate. Markers are not automatically interpreted.

`adc_to_mv: true` enables the historical 16-bit/3-V/1019-gain conversion. Use it
only for data acquired with those exact settings. It defaults to false. Numeric
malformed/nonfinite samples are rejected rather than silently deleted. Time
columns, where supplied, are checked for sampling continuity.

## Output and interpretation

Each run writes:

- `metrics.csv`: a row per recording/window, all 18 HRV fields, QC, original
  window boundaries, detector/polarity, pre-Malik and Malik comparisons.
- `diagnostics.csv`: omitted frequency estimates, warnings and processing errors.
- `summary.json`: counts and a reminder that rows may overlap.
- `provenance.json`: package/dependency versions, full resolved configuration,
  UTC time and SHA-256 hashes of inputs, manifest and configuration.

`HRV_MeanHR = 60000 / mean(valid RR in ms)`; it is not the average of beatwise
`60000/RR`. Other columns are MeanNN, MedianNN, SDNN, RMSSD, SDSD, CVNN, pNN50,
pNN20, LF, HF, LFHF, LFn, HFn, TP, SD1, SD2 and SD1SD2. Time/variability units
are milliseconds, HR is bpm, pNN values are percentages, LF/HF/TP are ms²,
and ratios/CVNN/normalized fractions are dimensionless.

`Usable` screens HRV, `Usable_HR` screens MeanHR, and `Usable_Frequency` requires
both HRV QC and computed frequency results. They are **heuristic labels**, not
proof of correct R-peak detection. `FullWindow` and `CrossLeadRequired` are explicit.
`MeanHR_SE` is a delta-method IID approximation; it is not an independently
validated measurement error or an autocorrelation-adjusted standard error.

`WindowMeanHR` uses equal weights across usable HR windows within one recording.
`MeanHR_demeaned` subtracts this reference. With overlap, this is not the
recording's duration-weighted mean HR. No participant-level pooling is implied.

### Malik comparison

`malik_mode` may be `off`, `compare` (default) or `on`:

- `compare`: primary `HRV_*` remains pre-Malik; `Malik_HRV_*` is a sensitivity comparison.
- `on`: primary metrics select the Malik values; pre-Malik values remain available.
- `off`: skips the optional comparison.

“BeforeMalik” is **after the configured detector's peak correction**, not fully
uncorrected ECG. Intervals outside RR bounds or >20% from a centered 11-interval
median are flagged. Interior intervals are interpolated between good anchors at
original timestamps; no edge extrapolation or reconstructed peak timeline.
QC always retains pre-Malik diagnostics; smoothing cannot rescue a failed record.
`ExtraRRInterpolation` describes the selected primary metrics, while
`MalikInterpolatedPct` describes the comparison. No automatic clinical ectopy
classification is performed.

### Frequency policy

By default every frequency metric requires **300 s between valid RR timestamps**.
A 300-s recording may contain slightly less than 300 s of RR timestamps and thus
produce blanks. 60-s windows intentionally have blank frequency fields. This is
a conservative project policy, not a universal minimum recording standard.
Change `frequency_min_span_s` only as a documented analysis choice. Absolute PSD
is requested (`normalize=False`); old normalized outputs are not interchangeable.
NeuroKit interpolates valid values at their observed timestamps; long gaps can
still bias spectra. The current QC does not validate spectral accuracy.

## Validation, development and release

```sh
python -m pytest -q
python -m build
python scripts/build_release.py
```

Tests cover RR adjacency, unchanged timestamps, Malik QC vetoes, missing leads,
window boundaries, invalid configurations, malformed inputs and synthetic CLI
runs. These tests verify specified software behavior, not physiological validity.
Real MRI peak accuracy, arrhythmia handling, clinical validity and cross-device
performance remain unvalidated. Manual expert annotation and independent
benchmarks are needed before stronger claims.

[GitHub Actions](.github/workflows/tests.yml) runs tests and a synthetic example
on Python 3.11 and 3.12. The workflow is supplied; local validation does not mean
GitHub-hosted CI has already run. The release script checks an allowlisted tree,
rejects unexpected data/binary files and creates a source ZIP plus checksums.

Do not initialize Git in the parent study-data directory. Initialize/upload only
this repository directory or the prepared release ZIP. Review the staged file
list before pushing. No GitHub repository is created or uploaded automatically.
See [contributing](CONTRIBUTING.md), [changelog](CHANGELOG.md) and
[release notes](docs/RELEASE_NOTES.md). Released under the [MIT license](LICENSE).
