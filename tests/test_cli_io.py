import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from ecg_hrv.cli import main
from ecg_hrv.config import Config
from ecg_hrv.io import load_signal,load_manifest,load_recording
from ecg_hrv.synthetic import generate


def test_escaped_mwi_and_gap(tmp_path):
    p=tmp_path/'ecg.txt'
    p.write_text('Sample Rate:\\t500\\r\\nTime (s)\\tECG_Ch1\\r\\n0\\t1\\r\\n0.002\\t2\\r\\n')
    x,fs=load_signal(p,{'format':'mwi'},1000)
    assert fs==500; np.testing.assert_equal(x,[1,2])
    p.write_text('Sample Rate: 500\nTime ECG\n0 1\n0.004 2\n')
    with pytest.raises(ValueError):load_signal(p,{'format':'mwi'},1000)


def test_ge_and_opensignals(tmp_path):
    p=tmp_path/'ge.txt';p.write_text('12\n13\n14\n')
    np.testing.assert_equal(load_signal(p,{'format':'ge'},1000)[0],[12,13,14])
    p.write_text('# synthetic header\n0 0 0 32768\n1 0 0 32768\n')
    x,_=load_signal(p,{'format':'opensignals','adc_to_mv':True},1000)
    np.testing.assert_equal(x,[0,0])


def test_manifest_duplicates_and_unknown(tmp_path):
    p=tmp_path/'manifest.json'
    p.write_text(json.dumps({'recordings':[{'id':'s','file':'x'},{'id':'s','file':'y'}]}))
    with pytest.raises(ValueError):load_manifest(p)
    p.write_text(json.dumps({'recordings':[{'id':'s','file':'x','guess_sync':True}]}))
    with pytest.raises(ValueError):load_manifest(p)


def test_synthetic_is_deterministic(tmp_path):
    a=generate(tmp_path/'a',duration=10);b=generate(tmp_path/'b',duration=10)
    assert (a/'lead1.csv').read_bytes()==(b/'lead1.csv').read_bytes()
    assert json.loads((a/'provenance.json').read_text())['synthetic'] is True


def test_cli_end_to_end_and_no_overwrite(tmp_path):
    data=generate(tmp_path/'data',duration=60)
    config=tmp_path/'config.json';config.write_text(json.dumps(Config().to_dict()))
    out=tmp_path/'out'
    args=['run','--config',str(config),'--manifest',str(data/'manifest.json'),'--output',str(out)]
    assert main(args)==0
    frame=pd.read_csv(out/'metrics.csv')
    assert len(frame)==1 and frame.Status.iloc[0]=='computed'
    assert 60<frame.HRV_MeanHR.iloc[0]<85
    assert frame.Malik_HRV_RMSSD.notna().all()
    assert len([c for c in frame if c.startswith('HRV_')])==18
    assert json.loads((out/'provenance.json').read_text())['package_version']=='0.1.0'
    assert main(args)==2


def test_failed_records_are_retained(tmp_path):
    m=tmp_path/'manifest.json';m.write_text(json.dumps({'recordings':[{'id':'synthetic-missing','file':'absent.csv'}]}))
    c=tmp_path/'config.json';c.write_text('{}')
    out=tmp_path/'results'
    assert main(['run','--config',str(c),'--manifest',str(m),'--output',str(out)])==2
    d=pd.read_csv(out/'metrics.csv')
    assert len(d)==1 and d.Status.iloc[0]=='error' and not d.Usable.iloc[0]


def test_manifest_offset_selection(tmp_path):
    p=tmp_path/'x.csv';pd.DataFrame({'ecg':np.arange(3000)}).to_csv(p,index=False)
    x,fs,other=load_recording({'file':'x.csv','start_s':1,'duration_s':1},tmp_path,Config())
    np.testing.assert_equal(x,np.arange(1000,2000));assert other is None and fs==1000
