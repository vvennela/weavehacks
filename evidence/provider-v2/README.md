# Revised provider check: passed

W&B Inference `openai/gpt-oss-20b` returned 30/30 schema-valid first responses with no retries. The check used the actual proposal, ranking, and final-selection schemas with 30 frozen synthetic cases.

The result saves each raw response, schema and case hashes, timing, validation, and separate context checks. A pass establishes compatibility with these schemas, not useful recommendations or search performance. The live agent experiment separately tested one recommendation against real GPU measurements.
