"""Compile existing measured sources for inspection only; never run a kernel."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile


def main():
    folder=Path(__file__).resolve().parent
    result=json.loads((folder/'search/result.json').read_text())
    spec=importlib.util.spec_from_file_location('object_reader',folder.parent/'cpu-libxsmm-editable-panel-2026-09-25/prepare.py')
    reader=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    flags=['-O3','-march=native','-ffast-math','-shared','-fPIC','-lm']
    summaries=[]
    texts=[]
    with tempfile.TemporaryDirectory(prefix='sera-strassen-codegen-') as scratch:
        for index in (1,3):
            trial=result['trials'][index]
            source=Path(trial['source'])
            assert hashlib.sha256(source.read_bytes()).hexdigest()==trial['source_hash']
            stem=f'trial-{index:03d}'
            library=Path(scratch)/(stem+'.so')
            subprocess.run(['clang',str(source),'-o',str(library),*flags],check=True)
            text=reader.text_section(library)
            texts.append(text)
            disassembly=reader.disassemble(library)
            (folder/(stem+'-compiled-disassembly.txt')).write_text(disassembly)
            asm=folder/(stem+'-compiler.s')
            subprocess.run(['clang','-O3','-march=native','-ffast-math','-fPIC','-S',str(source),'-o',str(asm)],check=True)
            assembly=asm.read_text()
            start=assembly.index('\n_gemm:')
            end=assembly.index('.cfi_endproc',start)+len('.cfi_endproc')
            gemm=assembly[start:end]
            (folder/(stem+'-gemm-compiler.txt')).write_text(gemm+'\n')
            summaries.append(dict(name=trial['name'],source_sha256=trial['source_hash'],
                compiled_text_bytes=len(text),compiled_text_sha256=hashlib.sha256(text).hexdigest(),
                disassembly_sha256=hashlib.sha256(disassembly.encode()).hexdigest(),
                compiler_assembly_sha256=hashlib.sha256(assembly.encode()).hexdigest(),
                gemm_assembly_sha256=hashlib.sha256(gemm.encode()).hexdigest(),
                static_call_site_counts={name:len(re.findall(r'\bbl\s+'+re.escape(name)+r'\b',gemm))
                    for name in ('_malloc','_free','_memcpy','_bzero','_sera_libxsmm_256')},
                gemm_assembly_lines=len(gemm.splitlines())))
    report=dict(compiler=subprocess.check_output(['clang','--version'],text=True).splitlines()[0],
        frozen_library_flags=flags, inspection_assembly_flags=['-O3','-march=native','-ffast-math','-fPIC','-S'],
        measured_sources=summaries,full_compiled_text_identical=texts[0]==texts[1],
        performance_measured=False,limitation='Compiler evidence alone does not measure component costs. Static call-site counts include fallback code and are not per-invocation counts.')
    (folder/'strassen-codegen.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
