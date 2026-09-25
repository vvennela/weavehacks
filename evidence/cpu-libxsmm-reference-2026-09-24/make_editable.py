"""Convert the pinned generated instructions to editable assembly, without changes."""
import json
from pathlib import Path
import re
import struct

folder = Path(__file__).resolve().parent
raw = (folder/'kernel-512.bin').read_bytes()
rows = []
targets = set()
for line in (folder/'disassembly.txt').read_text().splitlines():
    match = re.match(r'\s*([0-9a-f]+):\s+([0-9a-f]{8})\s+(.+)', line)
    if not match:
        continue
    address, word, instruction = int(match[1],16), int(match[2],16), match[3]
    if address >= len(raw):
        break
    assert struct.unpack_from('<I',raw,address)[0] == word
    instruction = instruction.split(';')[0].strip()
    branch = re.search(r'0x([0-9a-f]+) <[^>]+>', instruction)
    if branch:
        target = int(branch[1],16)
        assert 0 <= target < len(raw)
        targets.add(target)
        instruction = instruction[:branch.start()] + f'Llibxsmm_{target:x}' + instruction[branch.end():]
    rows.append((address,instruction))
assert len(rows)*4 == len(raw)
assembly = ['.text','.arch armv9-a+sme2','.p2align 12','_sera_libxsmm_512:']
for address,instruction in rows:
    if address in targets:
        assembly.append(f'Llibxsmm_{address:x}:')
    assembly.append(instruction)
source = (folder/'source/kernel.c').read_text()
start = source.index('__asm__(')
end = source.index('extern void sera_libxsmm_512',start)
source = source[:start]+'__asm__(\n'+''.join('    '+json.dumps(line+'\n')+'\n' for line in assembly)+');\n'+source[end:]
source = source.replace('Raw instructions retained exactly;', 'Editable assembly reassembled byte-for-byte;')
(folder/'editable').mkdir(exist_ok=True)
(folder/'editable/kernel.c').write_text(source)
