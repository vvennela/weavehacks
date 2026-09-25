# Sera CPU MatMul run

Status: running.

Goal: exceed 1,780 GFLOP/s on this M4 Pro under the unchanged single-threaded 512-square float32 hill. Three repeated official reports per source, paired with unchanged controls; one final held-out run. No best-of-repeats promotion. The hill itself retains its fixed best-of-three scoring rule.

Live state: search/result.json. Signed evaluator reports and source snapshots are in search/trial-*/. Codex prompts and responses are in agent/. This is a trusted local research run, not a sandboxed production service.

Status: completed. Target met: False.

- existing-sme: passed; scores=[946.5851659425534, 992.8264414285657, 1030.1302377943232]; controls=[]

- sme-contiguous-panels-unroll4: passed; scores=[1029.30861628746, 699.5826404204772, 712.975978506514]; controls=[1020.993226698264, 987.1962965261336, 639.9578723667391]

- sme-fused-a-panel-unroll2: passed; scores=[1059.2638449812466, 1114.6124152222114, 1053.2043173189027]; controls=[954.579708392969, 962.9971586156971, 1064.869323747484]

- sme-fused-a-panel-staged-loads: passed; scores=[1096.4022430767989, 1117.70336998328, 786.2415777368327]; controls=[1047.8924256617488, 1104.4863276208966, 1051.9990896867787]

- sme-fused-a-panel-wide-transpose: passed; scores=[1071.0641546955553, 1097.1461595788755, 1028.9811151544159]; controls=[1019.6978526905898, 634.91289707507, 977.312342312201]

- sme-fused-a-panel-four-step-row-pointers: passed; scores=[1065.7487211767823, 1020.0194702565424, 858.1943025803108]; controls=[862.7897420799369, 1021.8016214843294, 993.2857150700744]

- sme-fused-a-panel-paired-transpose: passed; scores=[972.1519719965307, 797.6284018676686, 987.1962965261336]; controls=[987.9556892330162, 917.0758934310688, 1036.098311671006]

Final GFLOP/s: 955.8510129383695. Winner: /Users/vishnuv/Documents/Documents/weavehacks/evidence/cpu-kernel-codex-2026-09-24-v2/search/trial-000/source/kernel.c
