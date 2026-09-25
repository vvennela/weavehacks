import importlib.util
from pathlib import Path

import pytest

FOLDER = Path(__file__).resolve().parent


def translator():
    spec = importlib.util.spec_from_file_location('prepare_panel', FOLDER/'prepare.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_branch_targets_become_labels_without_changing_instruction_count():
    module = translator()
    raw = bytes.fromhex('200000b5c0035fd6')
    text = '0: b5000020 cbnz x0, 0x4 <kernel+0x4>\n4: d65f03c0 ret\n'
    rows = module.decode(text, raw)
    assert rows == ['cbnz x0, Lpanel32_4', 'Lpanel32_4:', 'ret']


def test_rejects_disassembly_that_does_not_match_binary():
    module = translator()
    with pytest.raises(ValueError, match='bytes'):
        module.decode('0: d503201f nop\n', bytes.fromhex('c0035fd6'))


def test_rejects_branch_outside_helper():
    module = translator()
    with pytest.raises(ValueError, match='target'):
        module.decode('0: b5000040 cbnz x0, 0x8\n4: d65f03c0 ret\n', bytes.fromhex('400000b5c0035fd6'))


def test_full_text_extraction_includes_non_instruction_bytes(tmp_path):
    import subprocess
    module = translator()
    source = tmp_path/'padding.s'
    obj = tmp_path/'padding.o'
    source.write_text('.text\nret\n.space 8\n.long 0x12345678\n')
    subprocess.run(['clang', '-c', str(source), '-o', str(obj)], check=True)
    assert module.text_section(obj) == bytes.fromhex('c0035fd6') + bytes(8) + bytes.fromhex('78563412')
