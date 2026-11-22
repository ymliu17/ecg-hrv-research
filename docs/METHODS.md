# Computational contract

This release factors earlier study-specific processing into a configurable core.
It does not promise bitwise equivalence with historical tables or implement the
original BREATHE marker/acquisition-time heuristics. Study-specific segmentation,
lead ranking and cross-recording aggregation are intentionally explicit upstream
steps. Select the intended segment and lead pair in the manifest. The primary
lead is the manifest's `file`; there is no hidden “best lead” selection.

## Interval handling

RR = difference between consecutive detected sample positions / fs × 1000.
Default valid range is 300–1500 ms inclusive. MeanNN/MedianNN/SDNN use valid RR.
RMSSD, SDSD and pNN use differences only when both originally adjacent intervals
are valid. Excluding an interval never pairs its former neighbors.

- RMSSD = sqrt(mean(dRR²)). SDNN and SDSD use sample SD (`ddof=1`).
- pNN20/50 = 100 × mean(|dRR| > 20/50 ms); denominator is valid adjacent pairs.
- CVNN = SDNN / MeanNN. MeanHR = 60000 / MeanNN.
- SD1 = SDSD / sqrt(2); SD2 = sqrt(2 SDNN² − SDSD²/2).
  If SD2 variance is negative or the ratio denominator is zero, the result is
  blank; no artificial clipping to a positive value.
- LF/HF/LFn/HFn/LFHF/TP are taken from NeuroKit 0.2.13, with absolute PSD and
  original valid RR end timestamps. The package does not claim TP is a clinical
  standard total-power estimate for every duration. See the dependency's
  implementation: https://github.com/neuropsychology/NeuroKit/tree/v0.2.13/neurokit2/hrv

Malik comparison interpolates flagged RR values at fixed observed timestamps.
This is an interval-series sensitivity analysis; it is not a new physiological
peak train. No corrected-RR cumulative sum determines timestamps or windows.
NeuroKit's automatic peak correction remains enabled in lab and GE profiles.

## QC defaults

Lab HRV: >=30 peaks, >=30 seconds, >=20 valid RR, invalid RR <=30%, local-median
irregularity <=20%, median HR 40–120 bpm, RMSSD/MeanNN <=0.30.
`ArtifactPct` counts >20% local-median deviations; it is not a measured false
R-peak rate. It is computed before extra Malik interpolation.

HR QC additionally requires valid RR duration / window span >=0.8,
|MeanHR − MedianHR| <=5 bpm and approximate SE <=2 bpm. SE =
60000 / mean(RR)² × SD(RR) / sqrt(n), assuming IID intervals.

MRI presets add coverage and mean–median consistency to HRV QC. Whole MRI
presets also require SDNN >=10 ms and RMSSD >=5 ms to screen some periodic
artifact lock-on; they are heuristics, not universally appropriate physiology.
Whole MRI artifact threshold is 10%; BIOPAC whole-run RMSSD/MeanNN limit is 0.15.
MRI-window presets allow >=11 peaks / 10 valid RR and >=15 s, but final acceptance
still requires a complete requested 60-s window. GE configurations require a
companion median HR within 2 bpm; unavailable comparison fails acceptance.

`Usable_HR` and `Usable` serve different targets; neither substitutes for manual
R-peak review. Use the same preregistered thresholds across compared analyses.
Peak and RR quality, spectral reliability and biological plausibility are
related but distinct validation questions.

## Timestamp and loader boundaries

Each file/manifest entry is independent. No file-name suffix or modification
clock establishes continuity. A source offset is supplied in seconds; round to
the nearest sample for slicing. Window coordinates are relative to that selected
segment, and SourceWindowStart/EndSec add the supplied source offset.
Window peaks use half-open intervals [start, end); crossing-boundary RR are not
included. Detection is performed once on the selected analysis stretch. The
companion lead is assumed to share the source clock and must use the same fs.

This package rejects nonfinite samples and supplied nonuniform time columns.
Headerless formats cannot independently establish missing-sample timing. Their
configured sample rate and continuity are assumptions recorded by configuration.
Do not silently remove rows upstream.

## Release migration

This is a portable research release, not a replacement file-name scheme for
legacy study CSV consumers. There is no implicit task/session aggregation, no
participant discovery and no automatic best-lead choice. Localized legacy rules
must be adapted explicitly. All QC settings are configuration values, and the
new run manifest records versions and input hashes. Old caches are not reused.
