"""Validated JSON configuration. No mutable process-global thresholds."""
from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path

@dataclass(frozen=True)
class QC:
    rr_min_ms: float = 300.0
    rr_max_ms: float = 1500.0
    min_peaks: int = 30
    min_duration_s: float = 30.0
    min_valid_rr: int = 20
    max_invalid_pct: float = 30.0
    max_artifact_pct: float = 20.0
    min_hr_bpm: float = 40.0
    max_hr_bpm: float = 120.0
    max_rmssd_meannn: float = 0.30
    min_coverage: float = 0.8
    max_hr_consistency_bpm: float = 5.0
    max_hr_se_bpm: float = 2.0
    max_crosslead_hr_diff_bpm: float = 2.0
    min_sdnn_ms: float = 10.0
    min_rmssd_ms: float = 5.0

@dataclass(frozen=True)
class Config:
    profile: str = "lab"
    sampling_rate_hz: float = 1000.0
    malik_mode: str = "compare"
    malik_threshold: float = 0.2
    malik_window: int = 11
    frequency_min_span_s: float = 300.0
    fallback_detector: bool = True
    require_crosslead: bool = False
    max_duration_s: float | None = None
    window_s: float | None = None
    step_s: float | None = None
    qc: QC = field(default_factory=QC)

    def __post_init__(self):
        if self.profile not in ("lab", "mri_ge", "mri_biopac"):
            raise ValueError("profile must be lab, mri_ge or mri_biopac")
        if self.malik_mode not in ("off", "compare", "on"):
            raise ValueError("malik_mode must be off, compare or on")
        if not isinstance(self.require_crosslead,bool) or not isinstance(self.fallback_detector,bool):
            raise ValueError("Boolean config fields must use JSON true/false")
        for name,v in asdict(self).items():
            if isinstance(v,(float,int)) and not isinstance(v,bool):
                if not math.isfinite(v) or v <= 0:
                    raise ValueError(f"{name} must be finite and positive")
        for name,v in asdict(self.qc).items():
            if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or v < 0:
                raise ValueError(f"Invalid QC threshold: {name}")
        if self.sampling_rate_hz <= 80:
            raise ValueError("sampling_rate_hz must exceed 80 Hz")
        if (self.window_s is None) != (self.step_s is None):
            raise ValueError("window_s and step_s must both be supplied")
        if self.step_s is not None and self.step_s > self.window_s:
            raise ValueError("step_s cannot exceed window_s")
        if self.window_s and self.max_duration_s and self.max_duration_s < self.window_s:
            raise ValueError("max_duration_s must accommodate at least one window")
        if not isinstance(self.malik_window,int) or self.malik_window < 3 or self.malik_window%2!=1:
            raise ValueError("malik_window must be an odd integer >=3")
        if not 0 < self.malik_threshold < 1:
            raise ValueError("malik_threshold must be between 0 and 1")
        q=self.qc
        if not 0 < q.rr_min_ms < q.rr_max_ms or not 0 < q.min_hr_bpm < q.max_hr_bpm:
            raise ValueError("Invalid RR or HR bounds")
        if not 0 <= q.min_coverage <= 1:
            raise ValueError("min_coverage must be in [0,1]")
        if any(not 0 <= v <= 100 for v in (q.max_invalid_pct,q.max_artifact_pct)):
            raise ValueError("Percentage thresholds must be in [0,100]")

    def to_dict(self):
        return asdict(self)


def load_config(path):
    obj=json.loads(Path(path).read_text())
    obj['qc']=QC(**obj.get('qc',{}))
    return Config(**obj)
