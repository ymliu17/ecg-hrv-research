from dataclasses import replace
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
from ecg_hrv.config import Config,QC,load_config
from ecg_hrv.metrics import time_metrics,malik_interpolate,frequency_metrics
from ecg_hrv.processing import analyze_peaks,process_recording


def test_true_adjacency_and_meanhr():
    row,_,d=time_metrics(np.array([800.,900.,2000.,1000.,1100.]),Config())
    np.testing.assert_equal(d,[100,100])
    assert row['HRV_RMSSD']==100
    assert row['HRV_MeanHR']==60000/950


def test_malik_keeps_times_and_edges():
    rr=np.array([2000.,800.,800.,1200.,800.,800.,2000.]);t=np.cumsum(rr)/1000; old=t.copy()
    corrected,flags,changed=malik_interpolate(rr,t,Config())
    np.testing.assert_equal(t,old)
    assert corrected[3]==800 and corrected[0]==2000 and corrected[-1]==2000
    assert changed.sum()==1 and flags.sum()==3


def test_qc_cannot_be_rescued_by_smoothing():
    peaks=np.r_[0,np.cumsum(np.tile([800,800,1400,800,800,800,1400,800,800,800],10))]
    row=analyze_peaks(peaks,1000,100,Config(malik_mode='on'))
    assert row['Malik_HRV_RMSSD']<row['BeforeMalik_HRV_RMSSD']
    assert not row['Usable']
    assert row['HRV_RMSSD']==row['Malik_HRV_RMSSD']


def test_compare_and_off_do_not_change_primary():
    peaks=np.arange(0,61000,800)
    a=analyze_peaks(peaks,1000,60,Config())
    b=analyze_peaks(peaks,1000,60,Config(malik_mode='off'))
    assert a['HRV_MeanHR']==b['HRV_MeanHR']==75
    assert np.isnan(b['Malik_HRV_MeanHR'])
    assert not a['FrequencyComputed']


def test_frequency_uses_original_timestamps():
    rr=np.full(450,800.);rr[100]=2000;t=np.cumsum(rr)/1000
    seen={}
    def fake(peaks,**kwargs):
        seen.update(peaks); assert kwargs['normalize'] is False
        return pd.DataFrame({'HRV_'+c:[1.] for c in ['LF','HF','LFHF','LFn','HFn','TP']})
    with patch('ecg_hrv.metrics.nk.hrv_frequency',side_effect=fake):
        _,ok,_=frequency_metrics(rr,t,1000,Config())
    assert ok
    np.testing.assert_equal(seen['RRI_Time'],t[rr!=2000])


def test_frequency_failure_keeps_time_domain():
    peaks=np.arange(0,361000,800)
    with patch('ecg_hrv.metrics.nk.hrv_frequency',side_effect=RuntimeError('synthetic failure')):
        row=analyze_peaks(peaks,1000,361,Config())
    assert row['HRV_MeanHR']==75
    assert not row['FrequencyComputed'] and 'failed' in row['ProcessingNotes']


def window_config():
    return Config(profile='mri_ge',max_duration_s=300,window_s=60,step_s=30,
                  require_crosslead=True,qc=QC(min_valid_rr=10,min_peaks=11,min_duration_s=15))


def test_sliding_grid_and_missing_companion():
    peaks=np.arange(200,300000,800)
    with patch('ecg_hrv.processing.detect',return_value=(peaks,peaks,False,'test')):
        rows=process_recording(np.zeros(300000),1000,window_config())
    assert len(rows)==9
    assert [r['WindowStartSec'] for r in rows]==list(range(0,241,30))
    assert [r['WindowEndSec'] for r in rows]==list(range(60,301,30))
    assert all(r['OverlapFraction']==.5 and r['FullWindow'] for r in rows)
    assert all(r['Usable_HR_SingleLead'] and not r['Usable_HR'] for r in rows)


def test_matching_lead_and_partial_tail():
    peaks=np.arange(200,280000,800)
    with patch('ecg_hrv.processing.detect',return_value=(peaks,peaks,False,'test')):
        rows=process_recording(np.zeros(280000),1000,window_config(),np.zeros(280000))
    assert len(rows)==9 and rows[0]['Usable_HR']
    assert rows[-1]['SpanEndSec']==280 and not rows[-1]['Usable_HR']


def test_empty_tail_and_bad_lead():
    peaks=np.arange(200,60000,800)
    with patch('ecg_hrv.processing.detect',return_value=(peaks,peaks,False,'test')):
        rows=process_recording(np.zeros(60000),1000,window_config())
    assert len(rows)==9 and rows[-1]['Status']=='insufficient_peaks'
    assert not rows[-1]['Usable']
    assert not analyze_peaks(peaks,1000,60,window_config(),np.arange(200,60000,600))['Usable_HR']

@pytest.mark.parametrize('kwargs',[{'window_s':60},{'window_s':60,'step_s':70},
    {'sampling_rate_hz':0},{'malik_window':4},{'malik_threshold':2},{'profile':'unknown'},
    {'require_crosslead':'false'},{'frequency_min_span_s':float('nan')}])
def test_invalid_config(kwargs):
    with pytest.raises((ValueError,TypeError)): Config(**kwargs)


def test_thresholds_do_not_leak_between_runs():
    rr=np.array([800.,900.,1200.])
    a=time_metrics(rr,Config())[0]
    time_metrics(rr,Config(qc=QC(rr_max_ms=1000)))
    assert time_metrics(rr,Config())[0]==a
