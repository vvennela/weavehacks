"""Expose exact unused imported helpers; no kernel experiment is chosen."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

from sera.cpu_kernel_validation import validate_cpu_kernel


def compose(evidence):
    original = (evidence / 'cpu-libxsmm-editable-panel-2026-09-25/baseline/kernel.c').read_text()
    if hashlib.sha256(original.encode()).hexdigest() != '04fc3ff86669c2ca123e3b390b662637cd69c21f3d63fa26f7a5f0f0a882317c':
        raise ValueError('Original baseline source hash changed')
    primitives = evidence / 'cpu-libxsmm-transpose-primitives-2026-09-25'
    manifest = json.loads((primitives / 'verification.json').read_text())
    helpers = {}
    for item in manifest['variants']:
        variant = item['variant']
        source = (primitives / (variant + '.c')).read_text()
        if hashlib.sha256(source.encode()).hexdigest() != item['source_sha256']:
            raise ValueError('Imported helper source hash changed')
        helpers[variant] = source
    if set(helpers) != {'ta', 'tb', 'tt'}:
        raise ValueError('Unexpected helper set')
    declarations = ''.join(f'extern void sera_libxsmm_{v}(const void *parameters);\n'
                           for v in ('ta', 'tb', 'tt'))
    return declarations + original + '\n' + '\n'.join(helpers.values()), original, helpers


def main():
    folder = Path(__file__).resolve().parent
    source, original, helpers = compose(folder.parent)
    baseline = folder / 'baseline/kernel.c'
    baseline.parent.mkdir(exist_ok=True)
    baseline.write_text(source)
    assert len(source.encode()) <= 256000
    translator = folder.parent / 'cpu-libxsmm-editable-panel-2026-09-25/prepare.py'
    spec = importlib.util.spec_from_file_location('text_reader', translator)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    primitives = folder.parent / 'cpu-libxsmm-transpose-primitives-2026-09-25'
    binaries = {'nn': (primitives / 'nn.bin').read_bytes(),
                **{v: (primitives / (v + '.bin')).read_bytes() for v in helpers}}
    with tempfile.TemporaryDirectory(prefix='sera-optional-transpose-') as scratch:
        obj = Path(scratch) / 'baseline.o'
        subprocess.run(['clang','-O3','-march=native','-ffast-math','-fPIC',
                        '-c',str(baseline),'-o',str(obj)], check=True)
        text = reader.text_section(obj)
        offsets = {}
        for name, binary in binaries.items():
            assert text.count(binary) == 1, name
            offsets[name] = text.index(binary)
    correctness = validate_cpu_kernel(baseline, folder / 'baseline-correctness.json', timeout=120)
    assert correctness['passed']
    result = dict(baseline_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
        original_source_sha256=hashlib.sha256(original.encode()).hexdigest(),
        helpers_sha256={v:hashlib.sha256(s.encode()).hexdigest() for v,s in helpers.items()},
        source_bytes=len(source.encode()), compiled_text_bytes=len(text),
        exact_exported_bodies_found_at_offsets=offsets, original_gemm_source_unchanged=True,
        helpers_unused=True, correctness_passed=True, performance_measured=False,
        limitation='Added helpers change binary layout; measure a fresh baseline. No speedup claimed.')
    (folder / 'preparation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
