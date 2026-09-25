# Sera CPU MatMul run

Status: running.

Goal: exceed 1,780 GFLOP/s on this M4 Pro under the unchanged single-threaded 512-square float32 hill. Three repeated official reports per source, paired with unchanged controls; one final held-out run. No best-of-repeats promotion. The hill itself retains its fixed best-of-three scoring rule.

Live state: search/result.json. Signed evaluator reports and source snapshots are in search/trial-*/. Codex prompts and responses are in agent/. This is a trusted local research run, not a sandboxed production service.

Status: completed. Target met: False.

- existing-sme: passed; scores=[620.2412567098598, 1059.2637841553458, 1037.263336329251]; controls=[]

- sme-panel-pack-fused-unroll4: passed; scores=[1101.8387453444054, 851.6137084291054, 1014.2423146153016]; controls=[1060.1381476646065, 1048.9202132185542, 842.7003364868019]

- sme-2x2-two-step-register-pipeline: passed; scores=[978.3524815085025, 739.7463514928492, 1029.3125792708934]; controls=[1035.7664763501227, 879.0354765908729, 1015.6775657025122]

- sme-row-panel-pack: passed; scores=[1014.2385225918238, 920.2196861656419, 901.4223130361808]; controls=[822.684779349311, 1060.3098049990133, 892.4288345598962]

- sme-fused-transpose-1x4-tiles: passed; scores=[977.7573714827544, 591.5398423086745, 858.7653789760197]; controls=[1082.0388949142207, 782.4213344835282, 990.0800659241107]

- sme-full-transpose-padded-stride: passed; scores=[992.5217943371588, 1045.6840558269112, 1016.6391798847789]; controls=[1050.628026141138, 995.4368069746165, 818.5030886844471]

- sme-full-tile-staggered-unroll4: passed; scores=[900.2856080030509, 1028.1613822594277, 732.0960435749655]; controls=[991.4513784202941, 993.8998301725899, 1037.6001586716977]

Final GFLOP/s: 623.9652339523095. Winner: /Users/vishnuv/Documents/Documents/weavehacks/evidence/cpu-specialists-codex-2026-09-24/search/trial-000/source/kernel.c
