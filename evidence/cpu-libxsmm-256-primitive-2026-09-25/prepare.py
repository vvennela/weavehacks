"""Export a pinned standalone 256-square primitive; no performance measurement."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    folder = Path(__file__).resolve().parent
    upstream = Path('/tmp/sera-libxsmm-upstream')
    revision = '10490f10e79d4511f252c33279ef970a188cfab6'
    assert subprocess.check_output(['git','rev-parse','HEAD'], cwd=upstream, text=True).strip() == revision
    subprocess.run(['git','diff','--quiet'], cwd=upstream, check=True)
    library = upstream/'lib/libxsmm.a'
    library_hash = hashlib.sha256(library.read_bytes()).hexdigest()
    assert library_hash == 'a1d0cf95526fa72b27e3ea77462ef0e8def3f31594450988af3ac6bd5e6d7ac8'
    translator = folder.parent/'cpu-libxsmm-editable-panel-2026-09-25/prepare.py'
    spec = importlib.util.spec_from_file_location('translator', translator)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    notice = (folder.parent/'cpu-libxsmm-reference-2026-09-24/LICENSE.libxsmm.md').read_text()
    with tempfile.TemporaryDirectory(prefix='sera-libxsmm-256-') as scratch:
        scratch = Path(scratch)
        exporter = scratch/'export'
        subprocess.run(['clang','-O2','-I'+str(upstream/'include'),str(folder/'export.c'),
                        str(library),'-lm','-lpthread','-o',str(exporter)], check=True)
        metadata = json.loads(subprocess.check_output([str(exporter),str(folder/'kernel-256.bin')],text=True))
        assert metadata['target'] == 'appl_m4'
        assert metadata['nflops'] == 2*256**3
        assert [metadata[k] for k in ('parameter_size','a_offset','b_offset','c_offset')] == [176,32,80,128]
        binary = (folder/'kernel-256.bin').read_bytes()
        assert len(binary) == metadata['code_size']
        metadata.update(upstream_commit=revision, m=256, n=256, k=256,
                        lda=256, ldb=256, ldc=256, beta=0, trans_a=False, trans_b=False,
                        binary_sha256=hashlib.sha256(binary).hexdigest())
        (folder/'export.json').write_text(json.dumps(metadata,indent=2)+'\n')
        header = '/*\n'+notice+'\n*/\n__asm__(\n'+''.join('    '+json.dumps(s+'\n')+'\n' for s in
            ('.text','.arch armv9-a+sme2','.p2align 12','_sera_libxsmm_256:'))
        suffix = ');\nextern void sera_libxsmm_256(const void *parameters);\n'
        raw = header+''.join('    '+json.dumps(f'.long 0x{int.from_bytes(binary[i:i+4],"little"):08x}\n')+'\n'
                            for i in range(0,len(binary),4))+suffix
        raw_file = scratch/'raw.c'; raw_file.write_text(raw)
        raw_obj = scratch/'raw.o'
        flags = ['clang','-O3','-march=native','-ffast-math','-fPIC','-c']
        subprocess.run(flags+[str(raw_file),'-o',str(raw_obj)],check=True)
        assert helper.text_section(raw_obj) == binary
        lines = helper.decode(helper.disassemble(raw_obj), binary)
        lines = [line.replace('Lpanel32_', 'Lgemm256_') for line in lines]
        source = header+''.join('    '+json.dumps(line+'\n')+'\n' for line in lines)+suffix
        source_path = folder/'primitive.c'; source_path.write_text(source)
        editable_obj = scratch/'editable.o'
        subprocess.run(flags+[str(source_path),'-o',str(editable_obj)],check=True)
        assert helper.text_section(editable_obj) == binary
        relocations = subprocess.check_output([helper.OBJDUMP,'-r',str(editable_obj)],text=True)
        assert 'RELOCATION RECORDS' not in relocations
        (folder/'disassembly.txt').write_text(helper.disassemble(editable_obj))
        (folder/'relocations.txt').write_text(relocations)
    (folder/'probe.c').write_text('''/* Correctness-only dense row-major 256-square adapter. */
#include "primitive.c"
void probe(const float *A, const float *B, float *C) {
    const void *parameters[22] = {0};
    parameters[4] = B;
    parameters[10] = A;
    parameters[16] = C;
    sera_libxsmm_256(parameters);
}
''')
    result = dict(upstream_commit=revision,static_library_sha256=library_hash,
        exporter_sha256=hashlib.sha256((folder/'export.c').read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256(source.encode()).hexdigest(),binary_sha256=metadata['binary_sha256'],
        code_bytes=len(binary),byte_identical=True,no_body_relocations=True,
        no_external_calls_or_addresses=True,all_direct_branches_internal=True,no_x18=True,
        license_preserved=notice in source,performance_measured=False,
        compiler=subprocess.check_output(['clang','--version'],text=True).splitlines()[0])
    (folder/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
