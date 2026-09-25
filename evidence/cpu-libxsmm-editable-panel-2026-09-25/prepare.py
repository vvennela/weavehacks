"""Expose the pinned panel helper as byte-identical editable assembly."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import struct
import tempfile

OBJDUMP = '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/llvm-objdump'
ROW = re.compile(r'^\s*([0-9a-f]+):\s+([0-9a-f]{8})\s+(.+)$', re.M)


def decode(disassembly, binary):
    rows = [(int(a, 16), int(w, 16), text.split(';', 1)[0].strip())
            for a, w, text in ROW.findall(disassembly) if int(a, 16) < len(binary)]
    if [a for a, _, _ in rows] != list(range(0, len(binary), 4)):
        raise ValueError('Incomplete helper instruction addresses')
    if b''.join(w.to_bytes(4, 'little') for _, w, _ in rows) != binary:
        raise ValueError('Disassembly bytes differ from pinned binary')
    targets = set()
    instructions = {}
    for address, _, text in rows:
        opcode = text.split()[0]
        if opcode in {'bl', 'blr', 'br', 'adr', 'adrp', '.long'} or re.search(r'\b[wx]18\b', text):
            raise ValueError('Unsupported helper instruction')
        if opcode in {'b', 'cbz', 'cbnz', 'tbz', 'tbnz'} or opcode.startswith('b.'):
            match = re.search(r'0x([0-9a-f]+)(?:\s+<[^>]+>)?$', text)
            if not match:
                raise ValueError('Unrecognized branch target')
            target = int(match[1], 16)
            if target not in range(0, len(binary), 4):
                raise ValueError('Branch target outside helper')
            targets.add(target)
            text = text[:match.start()] + f'Lpanel32_{target:x}'
        instructions[address] = text
    output = []
    for address, _, _ in rows:
        if address in targets:
            output.append(f'Lpanel32_{address:x}:')
        output.append(instructions[address])
    return output


def disassemble(path):
    return subprocess.check_output([OBJDUMP, '-d', '--mattr=+sme,+sme2', str(path)], text=True)


def text_section(path):
    data = Path(path).read_bytes()
    if struct.unpack_from('<I', data)[0] != 0xFEEDFACF:
        raise ValueError('Expected little-endian 64-bit Mach-O')
    commands = struct.unpack_from('<I', data, 16)[0]
    offset = 32
    for _ in range(commands):
        command, size = struct.unpack_from('<II', data, offset)
        if command == 0x19:
            sections = struct.unpack_from('<I', data, offset+64)[0]
            for index in range(sections):
                section = offset+72+index*80
                name = data[section:section+16].rstrip(b'\0')
                segment = data[section+16:section+32].rstrip(b'\0')
                if (segment, name) == (b'__TEXT', b'__text'):
                    _, length, start = struct.unpack_from('<QQI', data, section+32)
                    if start+length > len(data):
                        raise ValueError('Text section exceeds object')
                    return data[start:start+length]
        offset += size
    raise ValueError('No text section')


def main():
    folder = Path(__file__).resolve().parent
    previous = folder.parent/'cpu-libxsmm-generator-2026-09-25'
    binary = (previous/'panel-32.bin').read_bytes()
    expected_hash = '60706b5ff14300b72eaccf91b992c248c3ee983ae57a97ce2449a57a61c38f4c'
    assert hashlib.sha256(binary).hexdigest() == expected_hash
    instructions = decode((previous/'disassembly.txt').read_text(), binary)
    raw = (previous/'panel_primitive.c').read_text()
    prefix, rest = raw.split('    ".long', 1)
    suffix = rest[rest.index(');'):]
    editable = prefix + ''.join('    '+json.dumps(line+'\n')+'\n' for line in instructions) + suffix
    (folder/'panel_primitive.c').write_text(editable)
    baseline = (previous/'baseline/kernel.c').read_text()
    assert baseline.count(raw) == 1
    (folder/'baseline').mkdir(exist_ok=True)
    (folder/'baseline/kernel.c').write_text(baseline.replace(raw, editable, 1))
    (folder/'panel_probe.c').write_text((previous/'panel_probe.c').read_text())
    with tempfile.TemporaryDirectory(prefix='sera-editable-panel-') as scratch:
        scratch = Path(scratch)
        for name, path in [('helper', folder/'panel_primitive.c'),
                           ('old', previous/'baseline/kernel.c'),
                           ('new', folder/'baseline/kernel.c')]:
            subprocess.run(['clang', '-O3', '-march=native', '-ffast-math', '-fPIC',
                            '-c', str(path), '-o', str(scratch/(name+'.o'))], check=True)
        helper = disassemble(scratch/'helper.o')
        assert text_section(scratch/'helper.o') == binary
        (folder/'disassembly.txt').write_text(helper)
        relocations = subprocess.check_output([OBJDUMP, '-r', str(scratch/'helper.o')], text=True)
        assert 'RELOCATION RECORDS' not in relocations
        (folder/'relocations.txt').write_text(relocations)
        old_bytes = text_section(scratch/'old.o')
        new_bytes = text_section(scratch/'new.o')
        assert old_bytes == new_bytes
        report = dict(helper_bytes=len(binary), helper_sha256=expected_hash,
                      helper_byte_identical=True, no_helper_relocations=True,
                      baseline_text_bytes=len(new_bytes), baseline_text_byte_identical=True,
                      baseline_text_sha256=hashlib.sha256(new_bytes).hexdigest(),
                      baseline_source_sha256=hashlib.sha256(baseline.replace(raw, editable, 1).encode()).hexdigest(),
                      previous_baseline_sha256=hashlib.sha256(baseline.encode()).hexdigest(),
                      transformation='Instruction spelling and local branch labels only; no instruction change',
                      compiler=subprocess.check_output(['clang','--version'],text=True).splitlines()[0])
        (folder/'byte-verification.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
