import csv

rows = list(csv.DictReader(open("05_screening/ai_discrepancy_review.csv", "r", encoding="utf-8")))

print("=== human_only → EXCLUDE (should be off-scope papers human mistakenly included) ===")
count = 0
for r in rows:
    if r["discrepancy_type"] == "human_only" and r["re_review_decision"] == "exclude":
        count += 1
        if count <= 10:
            print("---")
            print("title:", r["title"][:120])
            print("note:", r["notes"][:150])

print("\nTotal human_only excluded:", count)

print("\n=== ai_rescue → INCLUDE (AI rescued a paper human missed) ===")
count = 0
for r in rows:
    if r["discrepancy_type"] == "ai_rescue" and r["re_review_decision"] == "include":
        count += 1
        if count <= 10:
            print("---")
            print("title:", r["title"][:120])
            print("note:", r["notes"][:150])

print("\nTotal ai_rescue included:", count)

print("\n=== ai_rescue → EXCLUDE (AI was wrong, human exclude confirmed) ===")
count = 0
for r in rows:
    if r["discrepancy_type"] == "ai_rescue" and r["re_review_decision"] == "exclude":
        count += 1
        if count <= 10:
            print("---")
            print("title:", r["title"][:120])
            print("note:", r["notes"][:150])

print("\nTotal ai_rescue excluded:", count)
