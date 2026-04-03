"""One-off script to merge 17 title-duplicate pairs detected by test_no_duplicates.py.

Pair #15 (67ef832f18a2 / 1d49f2843829) excluded — different authors, same title.

Creates .csv.bak backups of every file before modifying.
"""

import csv
import shutil
from pathlib import Path

MERGES = {
    # drop_id -> keep_id
    "44997e238c7a": "47412220e1bb",
    "11aa443287c0": "d76ce1e8a91b",
    "b6a55230434d": "d919ba675da3",
    "eb9b2edee442": "9ee4aaf0f745",
    "deb2ea7baca5": "2b18608f6860",
    "081132e62980": "6cb040f251ff",
    "043b5343fb3d": "f96f14134a21",
    "5bd5a79bc18a": "88e1fac438e9",
    "3fe31dea1f88": "c7d33a63a50e",
    "146a99b9b311": "66f43397ba83",
    "f20042024dc6": "4ee4d5f63858",
    "cb8d976cb90c": "320ac2390210",
    "52b948ec890d": "9700e75505fd",
    "06019399445b": "56176dc5f8a2",
    "51c76454c0ce": "ff36740b3b52",
    "14777484b99d": "7055fc9f6caf",
    "70217d6e8f7f": "f3c77d3e6ee0",
}

DROP_IDS = set(MERGES.keys())
ROOT = Path(__file__).resolve().parent


def _backup(path: Path) -> None:
    shutil.copy2(path, path.with_suffix(".csv.bak"))


def _load(path: Path):
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def _save(path: Path, fields, rows) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    print(f"Merging {len(MERGES)} duplicate pairs\n")

    # 1. master_records.csv — set duplicate_of
    mr_path = ROOT / "04_deduped_library" / "master_records.csv"
    _backup(mr_path)
    fields, rows = _load(mr_path)
    n = 0
    for row in rows:
        pid = row["paper_id"]
        if pid in DROP_IDS and not row.get("duplicate_of", "").strip():
            row["duplicate_of"] = MERGES[pid]
            n += 1
    _save(mr_path, fields, rows)
    print(f"master_records.csv: marked {n} rows as duplicate_of")

    # 2. included_for_coding.csv — exclude dropped
    inc_path = ROOT / "05_screening" / "included_for_coding.csv"
    _backup(inc_path)
    fields, rows = _load(inc_path)
    n = 0
    for row in rows:
        if row["paper_id"] in DROP_IDS:
            if row.get("final_decision", "").strip().lower() == "include":
                row["final_decision"] = "exclude"
                n += 1
    _save(inc_path, fields, rows)
    print(f"included_for_coding.csv: excluded {n} dropped duplicates")

    # 3. title_abstract_decisions.csv — mark as duplicate
    ta_path = ROOT / "05_screening" / "title_abstract_decisions.csv"
    if ta_path.exists():
        _backup(ta_path)
        fields, rows = _load(ta_path)
        n = 0
        for row in rows:
            pid = row["paper_id"]
            if pid in DROP_IDS and row.get("final_decision", "").strip().lower() == "include":
                row["final_decision"] = "exclude"
                row["reason_code"] = "duplicate"
                keep_id = MERGES[pid]
                old_notes = row.get("notes", "").strip()
                note = f"Merged into {keep_id}"
                row["notes"] = f"{old_notes}; {note}".lstrip("; ")
                n += 1
        _save(ta_path, fields, rows)
        print(f"title_abstract_decisions.csv: updated {n} rows")

    # 4. topic_coding.csv — remove dropped rows
    tc_path = ROOT / "06_extraction" / "topic_coding.csv"
    if tc_path.exists():
        _backup(tc_path)
        fields, rows = _load(tc_path)
        before = len(rows)
        rows = [r for r in rows if r["paper_id"] not in DROP_IDS]
        _save(tc_path, fields, rows)
        print(f"topic_coding.csv: removed {before - len(rows)} dropped duplicates")

    # 5. tier_classification.csv — remove dropped rows
    tier_path = ROOT / "06_extraction" / "tier_classification.csv"
    if tier_path.exists():
        _backup(tier_path)
        fields, rows = _load(tier_path)
        before = len(rows)
        rows = [r for r in rows if r["paper_id"] not in DROP_IDS]
        _save(tier_path, fields, rows)
        print(f"tier_classification.csv: removed {before - len(rows)} dropped duplicates")

    # 6. download_log.csv — remove dropped rows
    dl_path = ROOT / "08_full_texts" / "download_log.csv"
    if dl_path.exists():
        _backup(dl_path)
        fields, rows = _load(dl_path)
        before = len(rows)
        rows = [r for r in rows if r["paper_id"] not in DROP_IDS]
        _save(dl_path, fields, rows)
        print(f"download_log.csv: removed {before - len(rows)} dropped duplicates")

    print("\nDone. Backup files (.csv.bak) created for all modified files.")


if __name__ == "__main__":
    main()
