"""Verify frozen input hashes, recompute results, and record a reproducible benchmark."""
import hashlib
import json
import platform
import time
import zipfile
from pathlib import Path
from observatory.backend.core import analyze, links

ROOT=Path(__file__).resolve().parents[2]


def main():
    data=ROOT/'observatory/public/data'
    manifest=json.loads((data/'manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['inputs']:
        actual=hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest()
        if actual!=entry['sha256']:raise ValueError('Input changed: '+entry['path'])
    records=json.loads((ROOT/'observatory/data/catalog.json').read_text(encoding='utf-8'))
    expected=json.loads((data/'analysis.json').read_text(encoding='utf-8'))
    start=time.perf_counter()
    actual=analyze(records,expected['coverage_start_ms'],expected['coverage_end_ms'])
    elapsed=time.perf_counter()-start
    assert actual==expected,'Analysis differs from published results'
    assets=json.loads((data/'assets.json').read_text(encoding='utf-8'))
    scenarios=json.loads((data/'scenarios.json').read_text(encoding='utf-8'))
    start=time.perf_counter()
    for i in range(100):links(scenarios[i%3]['event'],assets)
    spatial_ms=(time.perf_counter()-start)*10
    report=dict(python=platform.python_version(),platform=platform.system(),records=len(records),anchors=actual['all']['n'],
                full_analysis_seconds=round(elapsed,3),mean_reference_proximity_ms=round(spatial_ms,3),
                reference_proximity_iterations=100,input_hashes_verified=len(manifest['inputs']),reproduces_exactly=True,
                note='Single local run. In-memory great-circle benchmark; not a PostGIS query or cloud latency claim.')
    out=ROOT/'observatory/docs';out.mkdir(parents=True,exist_ok=True)
    (out/'benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
    archive=ROOT/'observatory/output/frozen-inputs.zip';archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted((ROOT/'observatory/data/raw').glob('*')):
            z.write(p,p.relative_to(ROOT))
        z.write(ROOT/'observatory/data/catalog.json','observatory/data/catalog.json')
        z.write(data/'manifest.json','observatory/public/data/manifest.json')
    print(json.dumps(report));print('Frozen archive bytes:',archive.stat().st_size)


if __name__=='__main__':main()
