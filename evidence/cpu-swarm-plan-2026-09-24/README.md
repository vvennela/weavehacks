# Preserved joint-planning attempt

Fifteen Luna specialists recommended experiments and then ranked the same 14-item board (one specialist abstained from proposing). Fourteen rankings were valid. `a_transpose` repeated an ID and omitted another, so this attempt stopped before candidate implementation or performance scoring. All failed artifacts remain unchanged.

The next AC run in `../cpu-swarm-ac-2026-09-24/` preserved this board and its 14 valid ballots, obtained one corrected ballot from the same specialist role, and established an entirely new AC baseline. Planning prompts here contain explicitly labeled historical battery results; those are not AC comparison evidence.

`assembly/comparison.json` and assembly files record a separate static compiler check: the baseline reduction loop has 15 instructions, while the earlier constant-512 candidate has 12 in its fast loop. This is a compiler-output fact, not a measured speedup. These files were produced after this planning prompt was submitted and were not supplied to its voters.
