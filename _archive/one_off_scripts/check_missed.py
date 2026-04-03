"""Check why Brandhofer et al. 2022 was missed."""
import pandas as pd

df = pd.read_csv("04_deduped_library/master_records.csv", dtype=str).fillna("")

# Search by DOI fragment
matches = df[df["doi"].str.contains("3213639", na=False)]
if len(matches) > 0:
    for _, r in matches.iterrows():
        print(f"DOI: {r['doi']}")
        print(f"Title: {r['title']}")
        print(f"Source: {r['source_db']}")
else:
    print("Not found by DOI fragment.")

# Search by author name
matches2 = df[
    df["title"].str.lower().str.contains("brandhofer", na=False)
    | df["authors"].str.lower().str.contains("brandhofer", na=False)
]
print(f"\nAuthor search 'brandhofer': {len(matches2)} matches")
for _, r in matches2.iterrows():
    print(f"  [{r['year']}] {r['title'][:100]} (DOI: {r['doi']}, src: {r['source_db']})")

# Search by partial title
matches3 = df[df["title"].str.lower().str.contains("portfolio.*vqe|vqe.*portfolio", na=False, regex=True)]
print(f"\nTitle search 'portfolio + VQE': {len(matches3)} matches")
for _, r in matches3.iterrows():
    print(f"  [{r['year']}] {r['title'][:100]} (DOI: {r['doi']}, src: {r['source_db']})")
