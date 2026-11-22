"""One peak train per recording; window slicing never changes peak timestamps."""
import warnings
import numpy as np
import neurokit2 as nk
from scipy.signal import butter, filtfilt, find_peaks
from scipy.stats import skew
from . import __version__
from .metrics import CORE, time_metrics, frequency_metrics, validity, artifact_fraction, malik_interpolate


def detect(x,fs,cfg):
    inverted=False
    if cfg.profile=='lab':
        oriented,inverted=nk.ecg_invert(x,sampling_rate=fs,show=False)
        cleaned=nk.ecg_clean(oriented,sampling_rate=fs)
    else:
        band=[5,20] if cfg.profile=='mri_ge' else [5,40]
        b,a=butter(3,band,btype='bandpass',fs=fs)
        cleaned=filtfilt(b,a,x)
        if cfg.profile=='mri_ge' and skew(cleaned)<0:
            cleaned=-cleaned; inverted=True
    if cfg.profile=='mri_biopac':
        height=.3*np.percentile(cleaned,99)
        peaks=find_peaks(cleaned,distance=int(.5*fs),height=height)[0] if height>0 else np.array([],int)
        return peaks,peaks.copy(),bool(inverted),'scipy_biopac'
    try:
        _,raw=nk.ecg_peaks(cleaned,sampling_rate=fs,correct_artifacts=False)
        _,fixed=nk.ecg_peaks(cleaned,sampling_rate=fs,correct_artifacts=True)
        peaks=np.asarray(fixed['ECG_R_Peaks'],dtype=int)
        if validity(np.diff(peaks)/fs*1000,cfg).sum()<2:
            raise ValueError('Insufficient valid RR after NeuroKit detection')
        return peaks,np.asarray(raw['ECG_R_Peaks'],dtype=int),bool(inverted),'neurokit'
    except Exception:
        if not cfg.fallback_detector or cfg.profile!='lab': raise
        b,a=butter(3,[5,40],btype='bandpass',fs=fs)
        filtered=filtfilt(b,a,-x if inverted else x)
        height=.3*np.percentile(filtered,99)
        peaks=find_peaks(filtered,distance=int(.5*fs),height=height)[0] if height>0 else np.array([],int)
        return peaks,peaks.copy(),bool(inverted),'scipy_fallback'


def empty_row(reason):
    row={'HRV_'+c:np.nan for c in CORE}
    for prefix in ('BeforeMalik_','Malik_'):
        row.update({prefix+'HRV_'+c:np.nan for c in CORE})
    row.update(Status='error',ProcessingNotes=reason,Usable=False,Usable_HR=False,
               Usable_Frequency=False,PipelineVersion=__version__,
               FrequencyComputed=False,MalikUsable=False)
    return row


def quality(rr,peaks,span,panel,other_hr,cfg):
    q=cfg.qc; mask=validity(rr,cfg); valid=rr[mask]; n=len(valid)
    hr=60000/np.median(valid) if n else np.nan
    invalid=100*(1-mask.mean()) if len(mask) else np.nan
    artifact=100*artifact_fraction(rr,cfg)
    coverage=valid.sum()/1000/span if span>0 else 0.
    consist=abs(panel['HRV_MeanHR']-hr)
    ratio=panel['HRV_RMSSD']/panel['HRV_MeanNN'] if n else np.nan
    se=60000/valid.mean()**2*valid.std(ddof=1)/np.sqrt(n) if n>1 else np.nan
    cross=abs(other_hr-hr) if other_hr is not None else np.nan
    cross_ok=not cfg.require_crosslead or (np.isfinite(cross) and cross<=q.max_crosslead_hr_diff_bpm)
    basic=(len(peaks)>=q.min_peaks and span>=q.min_duration_s and n>=q.min_valid_rr and
           invalid<=q.max_invalid_pct and artifact<=q.max_artifact_pct and q.min_hr_bpm<=hr<=q.max_hr_bpm)
    hr_single=bool(basic and coverage>=q.min_coverage and consist<=q.max_hr_consistency_bpm and se<=q.max_hr_se_bpm)
    usable=bool(basic and ratio<=q.max_rmssd_meannn and cross_ok)
    if cfg.profile!='lab':
        usable=bool(usable and coverage>=q.min_coverage and consist<=q.max_hr_consistency_bpm)
        if cfg.window_s is None:
            usable=bool(usable and panel['HRV_SDNN']>=q.min_sdnn_ms and panel['HRV_RMSSD']>=q.min_rmssd_ms)
    return dict(NPeaks=len(peaks),NRRI_raw=len(rr),NValidRRI=n,InvalidPct=invalid,
        ArtifactPct=artifact,MedianHR=hr,ValidRRCoverage=coverage,HRConsistency_bpm=consist,
        RMSSD_over_MeanNN=ratio,MeanHR_SE=se,MeanHR_SE_Method='delta_method_IID',
        CrossLeadHRDiff_bpm=cross,CrossLeadRequired=cfg.require_crosslead,
        CrossLeadOK=bool(cross<=q.max_crosslead_hr_diff_bpm) if np.isfinite(cross) else None,
        Usable_HR_SingleLead=hr_single,Usable_HR=bool(hr_single and cross_ok),Usable=usable)


def analyze_peaks(peaks,fs,span,cfg,other_peaks=None):
    rr=np.diff(peaks)/fs*1000; times=peaks[1:]/fs
    panel,valid,diffs=time_metrics(rr,cfg)
    f,fok,note=frequency_metrics(rr,times,fs,cfg); panel.update(f)
    other_hr=None
    if other_peaks is not None:
        ro=np.diff(other_peaks)/fs*1000; vo=validity(ro,cfg)
        if vo.sum()>=cfg.qc.min_valid_rr: other_hr=60000/np.median(ro[vo])
    qc=quality(rr,peaks,span,panel,other_hr,cfg)
    row=empty_row(''); row.update(qc)
    row.update({'BeforeMalik_'+k:v for k,v in panel.items()})
    row.update(BeforeMalikUsable=qc['Usable'],QCReference='post_detector_before_Malik',
               MalikMode=cfg.malik_mode,ExtraRRInterpolation=False)
    selected=panel
    if cfg.malik_mode!='off':
        corrected,flags,changed=malik_interpolate(rr,times,cfg)
        after,_,cdiffs=time_metrics(corrected,cfg)
        f,cfok,cnote=frequency_metrics(corrected,times,fs,cfg); after.update(f)
        cq=quality(corrected,peaks,span,after,other_hr,cfg)
        row.update({'Malik_'+k:v for k,v in after.items()})
        row.update(MalikFlaggedPct=100*flags.mean() if len(flags) else np.nan,
                   MalikInterpolatedPct=100*changed.mean() if len(changed) else np.nan,
                   MalikUnresolvedCount=int((flags&~changed).sum()),
                   MalikFrequencyComputed=cfok,MalikUsable=bool(qc['Usable'] and cq['Usable']))
        if cfg.malik_mode=='on':
            selected=after; diffs=cdiffs; fok=cfok; note=cnote
            row['Usable']=row['MalikUsable']
            row['Usable_HR']=bool(qc['Usable_HR'] and cq['Usable_HR'])
            row['ExtraRRInterpolation']=bool(changed.any())
    row.update(selected)
    row.update(MeanHR=selected['HRV_MeanHR'],FrequencyComputed=fok,
        Usable_Frequency=bool(row['Usable'] and fok),NValidAdjacentPairs=len(diffs),
        SumSquaredAdjacentDiffs=float(np.sum(diffs**2)),ProcessingNotes=note,
        Status='computed' if valid.any() else 'insufficient_peaks')
    return row


def process_recording(x,fs,cfg,other=None):
    x=np.asarray(x,dtype=float)
    if x.ndim!=1 or not np.isfinite(x).all() or len(x)<fs*10:
        raise ValueError('ECG must be a finite 1-D signal of at least 10 seconds')
    if not np.isfinite(fs) or fs<=80: raise ValueError('Invalid sampling rate')
    if other is not None:
        other=np.asarray(other,dtype=float)
        if other.ndim!=1 or not np.isfinite(other).all(): raise ValueError('Invalid companion lead')
    available=len(x)/fs
    analysis=min(available,cfg.max_duration_s) if cfg.max_duration_s else available
    # Detect once on the analysis stretch, never independently at each window edge.
    n=int(round(analysis*fs)); x=x[:n]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        peaks,before,inverted,detector=detect(x,fs,cfg)
        other_peaks=None; other_note=''
        if other is not None:
            try: other_peaks=detect(other[:n],fs,cfg)[0]
            except Exception as exc: other_note='Companion detection failed: '+type(exc).__name__
        if cfg.window_s is None:
            grid=[(0.,analysis)]
        else:
            horizon=cfg.max_duration_s or analysis
            count=max(0,int(np.floor((horizon-cfg.window_s)/cfg.step_s+1e-9))+1)
            grid=[(i*cfg.step_s,i*cfg.step_s+cfg.window_s) for i in range(count)]
        rows=[]
        for i,(start,end) in enumerate(grid):
            actual_end=max(start,min(end,analysis)); span=actual_end-start
            lo=int(round(start*fs)); hi=int(round(actual_end*fs))
            wp=peaks[(peaks>=lo)&(peaks<hi)]
            wo=None if other_peaks is None else other_peaks[(other_peaks>=lo)&(other_peaks<hi)]
            row=analyze_peaks(wp,fs,span,cfg,wo)
            full=bool(actual_end>=end-1e-9)
            if not full: row.update(Usable=False,Usable_HR=False,Usable_Frequency=False)
            raw=before[(before>=lo)&(before<hi)]
            row.update(WindowIdx=i,WindowStartSec=start,WindowEndSec=end,
                SpanEndSec=actual_end,SpanSec=span,FullWindow=full,
                WindowCenterSec=(start+end)/2,WindowLengthSec=end-start,
                WindowStepSec=cfg.step_s,OverlapFraction=0. if cfg.step_s is None else 1-cfg.step_s/cfg.window_s,
                SamplingRate=fs,Detector=detector,PolarityInverted=inverted,
                NPeaksBeforeCorrection=len(raw),ArtifactPctBeforeCorrection=100*artifact_fraction(np.diff(raw),cfg))
            row['ProcessingNotes']='; '.join(filter(None,[row['ProcessingNotes'],other_note]))
            rows.append(row)
    notes='; '.join(dict.fromkeys(str(w.message) for w in caught))
    for row in rows:
        row['ProcessingNotes']='; '.join(filter(None,[row['ProcessingNotes'],notes]))
    return rows
