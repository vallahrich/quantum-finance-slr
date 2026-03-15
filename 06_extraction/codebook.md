# Extraction Codebook

See extraction_template.xlsx Codebook sheet.

LLM-assisted thematic coding artifacts are generated separately in this folder:
- `topic_taxonomy.md`
- `topic_coding.csv`
- `topic_coding_summary.md`

These are draft analytical support files and should be reviewed before use in synthesis.

Operational notes:
- The recommended starting deployment for `topic-code` is `gpt-5-mini`.
- `topic-code` can read final includes from `05_screening/full_text_decisions.csv`.
- During interim analysis, `topic-code --input-file 05_screening/included_for_coding.csv` is also supported.
- Topic-coding outputs are resumable via `06_extraction/topic_coding_checkpoint.json` and logged to `06_extraction/topic_coding_prompt_log.jsonl`.
