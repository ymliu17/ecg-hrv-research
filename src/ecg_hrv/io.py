"""Explicit input formats. Never drop malformed samples or infer synchronization."""
from pathlib import Path
import json
import re
import numpy as np
import pandas as pd

FORMATS={'csv','ge','mwi','opensignals','acq'}


def load_signal(path,spec,default_fs):
    fmt=spec.get('format','csv'); fs=float(spec.get('sampling_rate_hz',default_fs))
    if fmt not in FORMATS: raise ValueError('Unknown input format')
    if fmt=='csv':
        df=pd.read_csv(path)
        col=spec.get('column','ecg'); x=df[col].to_numpy(dtype=float)
        timecol=spec.get('time_column')
        if timecol: _check_times(df[timecol].to_numpy(dtype=float),fs)
    elif fmt=='ge':
        x=pd.read_csv(path,header=None).iloc[:,0].to_numpy(dtype=float)
    elif fmt=='mwi':
        text=Path(path).read_text().replace('\\r\\n','\n').replace('\\n','\n').replace('\\t','\t')
        lines=text.splitlines(); match=re.search(r'\d+(?:\.\d+)?',lines[0])
        if not match: raise ValueError('Missing MWI sampling rate')
        fs=float(match.group())
        data=np.asarray([[float(v) for v in l.split()] for l in lines[2:] if l.strip()])
        _check_times(data[:,0],fs); x=data[:,int(spec.get('column',1))]
    elif fmt=='opensignals':
        df=pd.read_csv(path,sep=r'\s+',comment='#',header=None)
        x=df.iloc[:,int(spec.get('column',3))].to_numpy(dtype=float)
    else:
        try: import bioread
        except ImportError as exc: raise ValueError('Install the biopac extra for ACQ files') from exc
        acq=bioread.read(str(path)); channel=acq.channels[int(spec.get('column',0))]
        fs=float(channel.samples_per_second); x=np.asarray(channel.data,dtype=float)
    if not np.isfinite(fs) or fs<=80: raise ValueError('Invalid sampling rate')
    if x.ndim!=1 or not len(x) or not np.isfinite(x).all(): raise ValueError('Empty or nonfinite signal')
    if spec.get('adc_to_mv',False): x=((x/2**16-.5)*3/1019)*1000
    return x,fs


def _check_times(times,fs):
    if not np.isfinite(times).all() or (len(times)>1 and not np.allclose(np.diff(times),1/fs,atol=2e-6,rtol=.01)):
        raise ValueError('Nonuniform/missing sample times; no automatic compression')


def load_manifest(path):
    data=json.loads(Path(path).read_text())
    if set(data)!={'recordings'} or not isinstance(data['recordings'],list) or not data['recordings']:
        raise ValueError('Manifest must contain a nonempty recordings list')
    ids=set(); allowed={'id','file','second_file','format','column','time_column','sampling_rate_hz','adc_to_mv','start_s','duration_s'}
    for rec in data['recordings']:
        if not isinstance(rec,dict) or set(rec)-allowed: raise ValueError('Unknown recording fields')
        if not isinstance(rec.get('id'),str) or not rec['id'] or rec['id'] in ids: raise ValueError('Recording ids must be nonempty and unique')
        if not isinstance(rec.get('file'),str): raise ValueError('Each recording needs a file')
        for field in ('start_s','duration_s'):
            value=rec.get(field,0 if field=='start_s' else None)
            if value is not None and (not np.isfinite(value) or value<0 or (field=='duration_s' and value==0)):
                raise ValueError('Invalid recording time selection')
        ids.add(rec['id'])
    return data['recordings']


def load_recording(rec,root,cfg):
    x,fs=load_signal(root/rec['file'],rec,cfg.sampling_rate_hz)
    other=None
    if rec.get('second_file'):
        other,other_fs=load_signal(root/rec['second_file'],rec,cfg.sampling_rate_hz)
        if other_fs!=fs: raise ValueError('Companion lead sampling rate differs')
    start=int(round(rec.get('start_s',0)*fs))
    end=start+int(round(rec['duration_s']*fs)) if 'duration_s' in rec else len(x)
    if start>=len(x): raise ValueError('Analysis start is outside the recording')
    return x[start:end],fs,None if other is None else other[start:end]
