"""Dataset splitting with image-hash groups isolated across partitions."""
import random


def stratified_hash_split(records: list[dict], classes: list[str], seed: int = 42) -> tuple[list[int], list[int], list[int]]:
    by_class: dict[str, dict[str, list[int]]] = {name: {} for name in classes}
    for index, row in enumerate(records):
        by_class[row["label"]].setdefault(row["group"], []).append(index)
    partitions: list[list[int]] = [[], [], []]
    for offset, name in enumerate(classes):
        groups = list(by_class[name].values())
        if len(groups) < 3:
            raise ValueError(f"Class '{name}' needs at least 3 distinct image groups for train/validation/test; found {len(groups)}")
        random.Random(seed + offset).shuffle(groups)
        test_count = max(1, round(len(groups) * .15))
        validation_count = max(1, round(len(groups) * .15))
        if test_count + validation_count >= len(groups):
            test_count = validation_count = 1
        groups_by_split = (groups[test_count + validation_count:], groups[test_count:test_count + validation_count], groups[:test_count])
        for partition, groups_for_split in zip(partitions, groups_by_split):
            partition.extend(index for group in groups_for_split for index in group)
    return tuple(sorted(partition) for partition in partitions)  # type: ignore[return-value]
