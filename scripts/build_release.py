"""Create an allowlisted, synthetic-data-only source ZIP and SHA256 checksum.

Run from any working directory. Does not push, tag or create a GitHub repository.
This check reduces accidental inclusion; it is not a general secret detector.
"""
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT=Path(__file__).resolve().parents[1]
TOP={'README.md','LICENSE','CHANGELOG.md','CONTRIBUTING.md','pyproject.toml',
     'requirements-tested.txt','requirements-py311-tested.lock','MANIFEST.in','.gitignore'}
DIRS={'src','tests','configs','docs','examples','scripts','.github'}
SKIP={'.git','__pycache__','.pytest_cache','build','dist','outputs','.venv'}
EXT={'.py','.md','.json','.toml','.yml','.csv'}


def selected_files():
    files=[]
    for path in sorted(ROOT.rglob('*')):
        rel=path.relative_to(ROOT)
        if any(p in SKIP or p.endswith('.egg-info') for p in rel.parts):continue
        if len(rel.parts)>1 and rel.parts[:2]==('examples','generated'):continue
        if path.is_symlink():raise ValueError(f'Symlink in release tree: {rel}')
        if not path.is_file():continue
        if len(rel.parts)==1:
            if str(rel) not in TOP:raise ValueError(f'Unexpected top-level release file: {rel}')
        elif rel.parts[0] not in DIRS or path.suffix not in EXT:
            raise ValueError(f'Unexpected release file: {rel}')
        if path.suffix=='.csv' and rel.parts[:2]!=('examples','synthetic_smoke'):
            raise ValueError(f'Unapproved data table: {rel}')
        text=path.read_text(encoding='utf8')
        for prefix in ('/'+'Users'+'/', '/'+'home'+'/'):
            if prefix in text:raise ValueError(f'Local home path found in {rel}')
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',text):
            raise ValueError(f'Private key marker found in {rel}')
        files.append(path)
    data=ROOT/'examples'/'synthetic_smoke'
    provenance=json.loads((data/'provenance.json').read_text())
    if provenance.get('synthetic') is not True:
        raise ValueError('Example provenance is not explicitly synthetic')
    manifest=json.loads((data/'manifest.json').read_text())
    if any(not r['id'].startswith('synthetic-') for r in manifest['recordings']):
        raise ValueError('Example IDs are not synthetic IDs')
    # Re-generate and byte-compare all included synthetic data, rather than only
    # trusting a provenance flag that could accompany accidentally replaced files.
    import tempfile
    import sys
    sys.path.insert(0,str(ROOT/'src'))
    from ecg_hrv.synthetic import generate
    with tempfile.TemporaryDirectory() as temp:
        expected=generate(Path(temp)/'expected',provenance['duration_s'],
                          provenance['sampling_rate_hz'],provenance['seed'])
        for path in data.iterdir():
            reference=expected/path.name
            if not reference.is_file() or path.read_bytes()!=reference.read_bytes():
                raise ValueError(f'Synthetic fixture does not match generator: {path.name}')
    return files


def main():
    files=selected_files()
    dest=ROOT/'dist';dest.mkdir(exist_ok=True)
    archive=dest/'ecg-hrv-research-0.1.0-source.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for path in files:
            info=zipfile.ZipInfo('ecg-hrv-research-0.1.0/'+path.relative_to(ROOT).as_posix(),
                                 date_time=(2026,11,21,0,0,0))
            info.external_attr=0o644<<16
            z.writestr(info,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (dest/(archive.name+'.sha256')).write_text(digest+'  '+archive.name+'\n')
    print(f'Checked {len(files)} files; synthetic examples match generator.')
    print(archive.name)

if __name__=='__main__':main()
