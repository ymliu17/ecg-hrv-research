"""Single command-line entry point for lab, assessment, whole MRI and windows."""
import argparse
from datetime import datetime,timezone
from importlib.metadata import version
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from . import __version__
from .config import load_config
from .io import load_manifest,load_recording
from .processing import process_recording,empty_row
from .synthetic import generate


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def run(args):
    cfg=load_config(args.config); records=load_manifest(args.manifest)
    output=Path(args.output)
    # Never overwrite an old run or reuse results generated with different parameters.
    if output.exists(): raise ValueError('Output directory exists; select a new run directory')
    root=Path(args.manifest).resolve().parent
    rows=[]; inputs=[]; failures=0
    for rec in records:
        entry={'id':rec['id'],'files':[]}
        try:
            for key in ('file','second_file'):
                if rec.get(key): entry['files'].append({'role':key,'sha256':sha256(root/rec[key])})
            x,fs,other=load_recording(rec,root,cfg)
            result=process_recording(x,fs,cfg,other)
            if not result: result=[empty_row('Recording too short for any full window')]
        except Exception as exc:
            # Keep errors without leaking absolute source paths in public diagnostics.
            result=[empty_row(type(exc).__name__+': '+str(exc).replace(str(root),'[input]'))]
        if any(r['Status']=='error' for r in result): failures+=1
        for row in result:
            row['RecordingID']=rec['id']; row['SourceStartSec']=rec.get('start_s',0.)
            if 'WindowStartSec' in row:
                row['SourceWindowStartSec']=row['SourceStartSec']+row['WindowStartSec']
                row['SourceWindowEndSec']=row['SourceStartSec']+row['WindowEndSec']
            rows.append(row)
        inputs.append(entry)
    df=pd.DataFrame(rows)
    if 'MeanHR' not in df: df['MeanHR']=np.nan
    # Window-centering is a window-weighted descriptive reference, not scan-time mean.
    stats=df.loc[df.Usable_HR & df.MeanHR.notna()].groupby('RecordingID').MeanHR.agg(
        WindowMeanHR='mean',NWindowsInMean='size').reset_index()
    df=df.merge(stats,on='RecordingID',how='left')
    df['MeanHR_demeaned']=df.MeanHR-df.WindowMeanHR
    output.mkdir(parents=True)
    df.to_csv(output/'metrics.csv',index=False)
    df.loc[df.ProcessingNotes.fillna('').ne(''),['RecordingID','Status','ProcessingNotes']].to_csv(output/'diagnostics.csv',index=False)
    summary={'version':__version__,'recordings':len(records),'rows':len(df),'error_recordings':failures,
             'usable_hr_rows':int(df.Usable_HR.sum()),'usable_hrv_rows':int(df.Usable.sum()),
             'note':'Overlapping rows are not independent observations; QC is heuristic.'}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    provenance={'package_version':__version__,'utc':datetime.now(timezone.utc).isoformat(),
        'config':cfg.to_dict(),'config_sha256':sha256(args.config),'manifest_sha256':sha256(args.manifest),
        'inputs':inputs,'dependencies':{n:version(n) for n in ['numpy','pandas','scipy','neurokit2']}}
    (output/'provenance.json').write_text(json.dumps(provenance,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary,indent=2))
    return 2 if failures else 0


def main(argv=None):
    parser=argparse.ArgumentParser(prog='ecg-hrv',description=__doc__)
    parser.add_argument('--version',action='version',version=__version__)
    sub=parser.add_subparsers(dest='command',required=True)
    gen=sub.add_parser('synthetic',help='Generate only simulated ECG data')
    gen.add_argument('--output',required=True);gen.add_argument('--duration',type=float,default=360.)
    gen.add_argument('--sampling-rate',type=float,default=250.);gen.add_argument('--seed',type=int,default=2026)
    runparser=sub.add_parser('run',help='Process recordings described by a manifest')
    for opt in ('config','manifest','output'): runparser.add_argument('--'+opt,required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=='synthetic':
            print(generate(args.output,args.duration,args.sampling_rate,args.seed));return 0
        return run(args)
    except (ValueError,TypeError,KeyError,OSError,json.JSONDecodeError) as exc:
        print(f'Error: {exc}',file=sys.stderr);return 2

if __name__=='__main__': raise SystemExit(main())
