"""Deterministic analytic waveform, no human or animal recordings."""
import json
from pathlib import Path
import numpy as np
import pandas as pd


def generate(destination,duration=360.,fs=250.,seed=2026):
    if not np.isfinite(duration) or duration<10 or not np.isfinite(fs) or fs<=80:
        raise ValueError('Synthetic duration >=10 s and sampling rate >80 Hz required')
    dst=Path(destination); dst.mkdir(parents=True,exist_ok=False)
    rng=np.random.default_rng(seed)
    times=np.arange(int(round(duration*fs)))/fs
    x=.02*np.sin(2*np.pi*.2*times)+rng.normal(0,.003,len(times))
    beats=[]; t=1.
    while t<duration-.5:
        beats.append(t)
        for offset,amplitude,width in [(-.18,.12,.035),(-.025,-.15,.008),(0,1.,.012),(.03,-.2,.01),(.26,.25,.06)]:
            center=t+offset; lo=max(0,int((center-.3)*fs)); hi=min(len(x),int((center+.3)*fs))
            x[lo:hi]+=amplitude*np.exp(-.5*((times[lo:hi]-center)/width)**2)
        t+=.85+.04*np.sin(2*np.pi*.1*t)+.015*np.sin(2*np.pi*.25*t)
    for name,signal in [('lead1',x),('lead2',-.8*x+rng.normal(0,.002,len(x)))]:
        pd.DataFrame({'time_s':times,'ecg':signal}).to_csv(dst/(name+'.csv'),index=False,float_format='%.8f')
    pd.DataFrame({'r_peak_time_s':beats}).to_csv(dst/'reference_peaks.csv',index=False)
    manifest={'recordings':[dict(id='synthetic-001',file='lead1.csv',second_file='lead2.csv',
        format='csv',column='ecg',time_column='time_s',sampling_rate_hz=fs)]}
    (dst/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (dst/'provenance.json').write_text(json.dumps(dict(synthetic=True,seed=seed,
        duration_s=duration,sampling_rate_hz=fs,generator='analytic Gaussian P/QRS/T plus sinusoids and noise',
        limitations='Does not simulate MRI gradient artifacts, arrhythmias or clinical populations'),indent=2)+'\n')
    return dst
