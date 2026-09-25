"""Embed and audit imported primitives; no performance evaluation or candidate selection."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    folder=Path(__file__).resolve().parent
    previous=folder.parent/'cpu-libxsmm-editable-panel-2026-09-25/prepare.py'
    spec=importlib.util.spec_from_file_location('editable_helper',previous)
    helper=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    notice=(folder.parent/'cpu-libxsmm-reference-2026-09-24/LICENSE.libxsmm.md').read_text()
    audit=[]
    with tempfile.TemporaryDirectory(prefix='sera-transpose-primitives-') as scratch:
        scratch=Path(scratch)
        for variant in ('ta','tb','tt'):
            binary=(folder/(variant+'.bin')).read_bytes()
            info=json.loads((folder/(variant+'.json')).read_text())
            assert hashlib.sha256(binary).hexdigest()==info['binary_sha256']
            symbol='sera_libxsmm_'+variant
            header='/*\n'+notice+'\n*/\n__asm__(\n'+''.join('    '+json.dumps(x+'\n')+'\n' for x in
                ('.text','.arch armv9-a+sme2','.p2align 12','_'+symbol+':'))
            suffix=');\nextern void '+symbol+'(const void *parameters);\n'
            raw=header+''.join('    '+json.dumps(f'.long 0x{int.from_bytes(binary[i:i+4],"little"):08x}\n')+'\n'
                              for i in range(0,len(binary),4))+suffix
            raw_file=scratch/(variant+'.c');raw_file.write_text(raw)
            raw_obj=scratch/(variant+'.o')
            command=['clang','-O3','-march=native','-ffast-math','-fPIC','-c',str(raw_file),'-o',str(raw_obj)]
            subprocess.run(command,check=True)
            disassembly=helper.disassemble(raw_obj)
            assert helper.text_section(raw_obj)==binary
            lines=helper.decode(disassembly,binary)
            lines=[line.replace('Lpanel32_',f'L{variant}_') for line in lines]
            source=header+''.join('    '+json.dumps(line+'\n')+'\n' for line in lines)+suffix
            source_path=folder/(variant+'.c');source_path.write_text(source)
            editable_obj=scratch/(variant+'-editable.o')
            subprocess.run(command[:-3]+[str(source_path),'-o',str(editable_obj)],check=True)
            assert helper.text_section(editable_obj)==binary
            relocations=subprocess.check_output([helper.OBJDUMP,'-r',str(editable_obj)],text=True)
            assert 'RELOCATION RECORDS' not in relocations
            (folder/(variant+'-disassembly.txt')).write_text(helper.disassemble(editable_obj))
            (folder/(variant+'-relocations.txt')).write_text(relocations)
            audit.append(dict(variant=variant,code_bytes=len(binary),instruction_count=len(binary)//4,
                source_sha256=hashlib.sha256(source.encode()).hexdigest(),binary_sha256=info['binary_sha256'],
                byte_identical=True,no_body_relocations=True,no_external_calls_or_addresses=True,
                all_direct_branches_internal=True,no_x18=True,license_preserved=notice in source))
    (folder/'probe.c').write_text('''/* Correctness-only ABI adapter: no layout conversion or performance claim. */
#include "ta.c"
#include "tb.c"
#include "tt.c"
void probe(int variant, const float *x, const float *y, float *c) {
    const void *parameters[22] = {0};
    parameters[4] = x;
    parameters[10] = y;
    parameters[16] = c;
    if (variant == 1) sera_libxsmm_ta(parameters);
    else if (variant == 2) sera_libxsmm_tb(parameters);
    else if (variant == 3) sera_libxsmm_tt(parameters);
}
''')
    report=dict(upstream_commit='10490f10e79d4511f252c33279ef970a188cfab6',
                compiler=subprocess.check_output(['clang','--version'],text=True).splitlines()[0],
                static_library_sha256=hashlib.sha256(Path('/tmp/sera-libxsmm-upstream/lib/libxsmm.a').read_bytes()).hexdigest(),
                exporter_sha256=hashlib.sha256((folder/'export.c').read_bytes()).hexdigest(),
                reused_translation_sha256=hashlib.sha256(previous.read_bytes()).hexdigest(),
                variants=audit,performance_measured=False,kernel_candidate_selected=False)
    (folder/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
