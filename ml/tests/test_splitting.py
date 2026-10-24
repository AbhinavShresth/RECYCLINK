import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.splitting import stratified_hash_split


def test_stratified_hash_groups_have_no_cross_split_leakage_and_repeat():
    rows = []
    for label in ("paper", "plastic"):
        for group in range(20):
            rows.append({"label": label, "group": f"{label}-{group}"})
            if group == 0:  # exact duplicate, remains in one partition
                rows.append({"label": label, "group": f"{label}-{group}"})
    first = stratified_hash_split(rows, ["paper", "plastic"])
    assert first == stratified_hash_split(rows, ["paper", "plastic"])
    partitions = [set(split) for split in first]
    assert not (partitions[0] & partitions[1] or partitions[0] & partitions[2] or partitions[1] & partitions[2])
    group_sets = [{rows[i]["group"] for i in split} for split in first]
    assert not (group_sets[0] & group_sets[1] or group_sets[0] & group_sets[2] or group_sets[1] & group_sets[2])
    assert all(any(rows[i]["label"] == label for i in split) for split in first for label in ("paper", "plastic"))


def test_class_with_too_few_distinct_groups_is_not_silently_split():
    rows = [{"label": "paper", "group": "same"}] * 5
    try:
        stratified_hash_split(rows, ["paper"])
        assert False, "duplicate copies should not count as independent samples"
    except ValueError as exc:
        assert "3 distinct image groups" in str(exc)
