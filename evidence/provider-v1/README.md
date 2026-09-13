# Initial provider check: failed

W&B Inference `openai/gpt-oss-20b` returned 19/30 valid first responses and 22/30 valid responses within one retry. The acceptance rule required at least 29 first-pass successes and all 30 within one retry.

Failures included inconsistent proposal action/cost fields and truncated ranking responses. Validation rejected them; these responses did not control GPU trials. The complete attempt history is preserved in result.json.

The next revision expressed cross-field constraints in the wire schema and bounded rankings to the one-candidate budget. See provider-v2 for the separate rerun; this failed record remains unchanged.
