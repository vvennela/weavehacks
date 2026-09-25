"""Compute-only calibration; never replaces or modifies the official GEMM hill."""
import ctypes
import hashlib
import json
from pathlib import Path
import platform
from statistics import median
import subprocess
import tempfile
import time

from examples.optimize_cpu_kernel import host_observation,check_power,power_source

FOLDER=Path(__file__).resolve().parent
ITERATIONS=200000
WARMUP_ITERATIONS=10000
ROUNDS=10
FMOPA_PER_ITERATION=64
FLAGS=['-O3','-march=native','-shared','-fPIC']
OBJDUMP='/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/llvm-objdump'


def main():
    result_path=FOLDER/'results.json'
    if result_path.exists():raise FileExistsError('Refusing to overwrite calibration')
    initial=host_observation()
    records=[]
    with tempfile.TemporaryDirectory(prefix='sera-peak-') as scratch:
        library=Path(scratch)/'probe.so'
        subprocess.run(['clang',*FLAGS,str(FOLDER/'probe.S'),'-o',str(library)],check=True)
        disassembly=subprocess.check_output([OBJDUMP,'-d','--mattr=+sme,+sme2',str(library)],text=True)
        assert disassembly.count('fmopa')==3*FMOPA_PER_ITERATION
        (FOLDER/'disassembly.txt').write_text(disassembly)
        loaded=ctypes.CDLL(str(library))
        functions={}
        output=(ctypes.c_float*256)()
        for tiles in (1,2,4):
            function=getattr(loaded,f'sera_peak_{tiles}')
            function.argtypes=[ctypes.c_uint64,ctypes.POINTER(ctypes.c_float)]
            function.restype=ctypes.c_uint64
            functions[tiles]=function
            assert function(WARMUP_ITERATIONS,output)==16
        for round_index in range(ROUNDS):
            before=host_observation();check_power(before,initial)
            order=(1,2,4)
            shift=round_index%len(order)
            for tiles in order[shift:]+order[:shift]:
                start=time.perf_counter_ns()
                lanes=functions[tiles](ITERATIONS,output)
                elapsed_ns=time.perf_counter_ns()-start
                assert lanes==16
                expected=ITERATIONS*FMOPA_PER_ITERATION//tiles
                assert list(output)[:tiles*lanes]==[float(expected)]*(tiles*lanes)
                flops=ITERATIONS*FMOPA_PER_ITERATION*2*lanes*lanes
                records.append(dict(round=round_index,tiles=tiles,lanes=lanes,iterations=ITERATIONS,
                    flops=flops,elapsed_ns=elapsed_ns,gflops=flops/elapsed_ns,output_verified=True))
            after=host_observation();check_power(after,initial)
            (FOLDER/f'round-{round_index:02d}.host.json').write_text(json.dumps(dict(before=before,after=after),indent=2)+'\n')
    summary={str(tiles):dict(minimum=min(r['gflops'] for r in records if r['tiles']==tiles),
        median=median(r['gflops'] for r in records if r['tiles']==tiles),
        maximum=max(r['gflops'] for r in records if r['tiles']==tiles)) for tiles in (1,2,4)}
    result=dict(kind='compute-only SME calibration, not GEMM or a hill score',hardware=platform.machine(),
        cpu=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
        compiler=subprocess.check_output(['clang','--version'],text=True).splitlines()[0],flags=FLAGS,
        source_sha256=hashlib.sha256((FOLDER/'probe.S').read_bytes()).hexdigest(),
        disassembly_sha256=hashlib.sha256(disassembly.encode()).hexdigest(),host=initial,power=power_source(initial),
        iterations=ITERATIONS,warmup_iterations_per_variant=WARMUP_ITERATIONS,rounds=ROUNDS,
        fmopa_per_iteration=FMOPA_PER_ITERATION,source_inputs='all FP32 ones; ZA zeroed on each invocation',
        thread_count=1,power_settings_changed=False,core_affinity_requested=False,qos_changed=False,
        timing='perf_counter_ns around one native call; includes entry/exit, state save/restore and final row stores',
        limitation='Register-only operands; no matrix packing or normal GEMM memory traffic. Measured reference, not a proven physical ceiling.',
        summary=summary,records=records)
    result_path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
