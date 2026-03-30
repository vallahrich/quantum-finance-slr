"""Update included_for_coding.csv from resolved ai_discrepancy_review.csv."""
import csv
from pathlib import Path

DISCREPANCY_CSV = Path("05_screening/ai_discrepancy_review.csv")
INCLUDED_CSV = Path("05_screening/included_for_coding.csv")

# Collect all paper_ids resolved to include
includes = []
with open(DISCREPANCY_CSV, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row["re_review_decision"].strip().lower() == "include":
            includes.append(row["paper_id"].strip())

# Deduplicate and sort for reproducibility
includes = sorted(set(includes))

# Write
with open(INCLUDED_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["paper_id", "final_decision"])
    for pid in includes:
        writer.writerow([pid, "include"])

print("Updated included_for_coding.csv: %d papers" % len(includes))
print("Previous count was 601, new count is %d" % len(includes))
