# GPT-6 Luna audit of remaining descriptor experiments

TA and TT full-call wrappers remain unmeasured. On the first board, the selected proposals scored 119 points (n512_fast_path), 101 (assembly_audit), and 100 (cache_conflict_layout). The TA proposal scored 46 and TT scored 40. Their lower rankings are not measurements.

The first TB proposal used an identity linear copy and Astra correctly abstained. The separate, correctly mapped TB proposal was implemented and measured. The first TA proposal also had a mapping error: it converted both inputs and passed converted A although TA requires original A. The TT proposal specified the correct two physical transposes but was not selected.

Correct full-call mappings, with each buffer newly allocated and filled inside gemm:

| Descriptor | Physical conversion | params[4] | params[10] | params[16] | Status |
| --- | --- | --- | --- | --- | --- |
| NN | None | original B | original A | original C | Imported reference |
| TA | bt[k*512+j] = B[j*512+k] | bt | original A | original C | Full-call wrapper unmeasured |
| TB | at[k*512+i] = A[i*512+k] | original B | at | original C | One wrapper measured; no promotion |
| TT | Both above conversions | bt | at | original C | Full-call wrapper unmeasured |

Each buffer is 1 MiB. TA retains generated B packing and adds generated A packing. TB skips B packing without adding A packing. TT skips B packing and adds A packing. These implementation facts do not predict whether the full timed call wins. Primitive correctness tests used prepared inputs and did not measure conversion cost. All allocation, conversion and free remain timed; no input reuse or caching is allowed.

The second board selected an already-existing store order with incorrect tile dimensions. The third board abstained. Some advisors correctly ruled out repeats, but the assertion that all legal transpose descriptors were already measured is false. The valid TB result does not establish a result for TA or TT. Correct this evidence inventory for the next board; do not select an order or change budgets, gates, or model architecture.
