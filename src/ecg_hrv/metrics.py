"""Valid-RR HRV formulas and spectral interpolation at observed timestamps."""
import numpy as np
import pandas as pd
import neurokit2 as nk


def validity(rri,cfg):
    return np.isfinite(rri) & (rri>=cfg.qc.rr_min_ms) & (rri<=cfg.qc.rr_max_ms)


def successive_diffs(rri,valid):
    return np.diff(rri)[valid[:-1]&valid[1:]]


def artifact_fraction(rri,cfg):
    if len(rri)<3: return np.nan
    med=pd.Series(rri).rolling(cfg.malik_window,center=True,min_periods=1).median().to_numpy()
    return float(np.mean(np.abs(rri-med)>cfg.malik_threshold*med))

CORE = ['MeanHR', 'MeanNN', 'MedianNN', 'SDNN', 'RMSSD', 'SDSD', 'CVNN',
        'pNN50', 'pNN20', 'LF', 'HF', 'LFHF', 'LFn', 'HFn', 'TP',
        'SD1', 'SD2', 'SD1SD2']
FREQ = ['LF', 'HF', 'LFHF', 'LFn', 'HFn', 'TP']
MIN_FREQ_S = 300.0



def time_metrics(rri, cfg):
    """Same valid RR set for level/variance; only truly adjacent valid pairs."""
    valid = validity(rri, cfg)
    rr = rri[valid]
    d = successive_diffs(rri, valid)
    out = {'HRV_' + name: np.nan for name in CORE}
    if len(rr):
        out.update(HRV_MeanNN=float(rr.mean()), HRV_MedianNN=float(np.median(rr)),
                   HRV_MeanHR=float(60000 / rr.mean()))
    if len(rr) > 1:
        sd = float(rr.std(ddof=1))
        out.update(HRV_SDNN=sd, HRV_CVNN=sd / rr.mean())
    if len(d):
        out.update(HRV_RMSSD=float(np.sqrt(np.mean(d ** 2))),
                   HRV_pNN50=float(100 * np.mean(np.abs(d) > 50)),
                   HRV_pNN20=float(100 * np.mean(np.abs(d) > 20)))
    if len(d) > 1 and len(rr) > 1:
        sdsd = float(d.std(ddof=1))
        sd1 = sdsd / np.sqrt(2)
        var2 = 2 * rr.var(ddof=1) - .5 * sdsd ** 2
        sd2 = np.sqrt(var2) if var2 >= 0 else np.nan
        out.update(HRV_SDSD=sdsd, HRV_SD1=sd1, HRV_SD2=sd2,
                   HRV_SD1SD2=sd1 / sd2 if sd2 > 0 else np.nan)
    return out, valid, d


def malik_interpolate(rri, times, cfg):
    threshold, window = cfg.malik_threshold, cfg.malik_window
    """Return RR, flag mask and actual replacement mask; no edge extrapolation."""
    rri = np.asarray(rri, dtype=float)
    median = pd.Series(rri).rolling(window, center=True, min_periods=1).median().to_numpy()
    flagged = (~validity(rri, cfg)) | (np.abs(rri - median) > threshold * median)
    anchors = ~flagged & np.isfinite(rri)
    changed = np.zeros(len(rri), dtype=bool)
    result = rri.copy()
    if anchors.sum() >= 2:
        changed = flagged & (times > times[anchors][0]) & (times < times[anchors][-1])
        result[changed] = np.interp(times[changed], times[anchors], rri[anchors])
    return result, flagged, changed


def frequency_metrics(rri, times, fs, cfg):
    """Absolute PSD (ms^2); preserve observed timestamps through interpolation.

    Default conservative policy: 300 s for all frequency metrics.
    The time grid is never rebuilt from corrected RR values.
    """
    out = {'HRV_' + c: np.nan for c in FREQ}
    valid = validity(rri, cfg)
    if valid.sum() < 2 or np.ptp(times[valid]) < cfg.frequency_min_span_s:
        return out, False, f'Frequency omitted: valid RR timestamp span <{cfg.frequency_min_span_s:g} s'
    try:
        frame = nk.hrv_frequency({'RRI': rri[valid], 'RRI_Time': times[valid]},
                                 sampling_rate=fs, show=False, normalize=False)
        out = {c: float(frame[c].iloc[0]) for c in out}
        return out, all(np.isfinite(v) for v in out.values()), ''
    except Exception as exc:
        return out, False, f'Frequency failed: {exc}'

