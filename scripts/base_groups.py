from collections import defaultdict

from decision_index.suite.build.rebuild import BUILDERS


def base_builder_groups() -> list[dict]:
    grouped = defaultdict(list)
    builders = {}

    for catalog_id, builder in BUILDERS.items():
        identity = (builder.__module__, builder.__qualname__)
        grouped[identity].append(int(catalog_id))
        builders[identity] = builder

    groups = []
    for identity, catalog_ids in grouped.items():
        catalog_ids = sorted(catalog_ids)
        builder = builders[identity]
        groups.append(
            {
                "key": "-".join(f"{catalog_id:03d}" for catalog_id in catalog_ids),
                "catalog_ids": catalog_ids,
                "builder": f"{builder.__module__.rsplit('.', 1)[-1]}.{builder.__name__}",
            }
        )

    return sorted(groups, key=lambda group: group["catalog_ids"])
