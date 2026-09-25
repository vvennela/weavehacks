"""Add an unused, exact imported 256-square helper without choosing an experiment."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

from sera.cpu_kernel_validation import validate_cpu_kernel


def compose(evidence):
    original = (evidence/'cpu-libxsmm-transpose-swarm-2026-09-25/baseline/kernel.c').read_text()
    if hashlib.sha256(original.encode()).hexdigest() != '67da75dd729b153a2129f8b1a71dd77b4d01609a94b6d2909ae69d99974fbdae':
        raise ValueError('Original baseline source hash changed')
    primitive = evidence/'cpu-libxsmm-256-primitive-2026-09-25'
    helper = (primitive/'primitive.c').read_text()
    manifest = json.loads((primitive/'verification.json').read_text())
    if hashlib.sha256(helper.encode()).hexdigest() != manifest['source_sha256']:
        raise ValueError('Imported helper source hash changed')
    declaration = 'extern void sera_libxsmm_256(const void *parameters);\n'
    return declaration + original + '\n' + helper, original, helper


def main():
    folder = Path(__file__).resolve().parent
    source, original, helper = compose(folder.parent)
    baseline = folder/'baseline/kernel.c'
    baseline.parent.mkdir(exist_ok=True)
    baseline.write_text(source)
    assert len(source.encode()) <= 256000
    translator = folder.parent/'cpu-libxsmm-editable-panel-2026-09-25/prepare.py'
    spec = importlib.util.spec_from_file_location('text_reader', translator)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    primitives = folder.parent/'cpu-libxsmm-transpose-primitives-2026-09-25'
    binaries = {v: (primitives/(v+'.bin')).read_bytes() for v in ('nn','ta','tb','tt')}
    binaries['n256'] = (folder.parent/'cpu-libxsmm-256-primitive-2026-09-25/kernel-256.bin').read_bytes()
    with tempfile.TemporaryDirectory(prefix='sera-optional-256-') as scratch:
        obj = Path(scratch)/'baseline.o'
        subprocess.run(['clang','-O3','-march=native','-ffast-math','-fPIC',
                        '-c',str(baseline),'-o',str(obj)], check=True)
        text = reader.text_section(obj)
        offsets = {}
        for name, binary in binaries.items():
            assert text.count(binary) == 1, name
            offsets[name] = text.index(binary)
    correctness = validate_cpu_kernel(baseline, folder/'baseline-correctness.json', timeout=120)
    assert correctness['passed']
    result = dict(baseline_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
        original_source_sha256=hashlib.sha256(original.encode()).hexdigest(),
        helper_sha256=hashlib.sha256(helper.encode()).hexdigest(),
        source_bytes=len(source.encode()), compiled_text_bytes=len(text),
        exact_exported_bodies_found_at_offsets=offsets, original_gemm_source_unchanged=True,
        helper_unused=True, correctness_passed=True, performance_measured=False,
        limitation='Added helper changes binary layout; measure a fresh baseline. No speedup claimed.')
    (folder/'preparation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
