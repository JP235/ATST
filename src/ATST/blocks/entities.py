from dataclasses import dataclass, field

from ATST.blocks import ENTITIES
from ATST.blocks.base_classes import WideTable, Block


@dataclass
class EntityTable(WideTable):
    table_name: str = ""
    pk: str = ""


@dataclass
class Entities(Block):
    name = ENTITIES
    tables: dict[str, EntityTable] = field(default_factory=dict)

    def __getattr__(self, name: str) -> EntityTable:
        if name.startswith("_"):
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )

        if name in self.tables:
            return self.tables[name]

        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(self.tables.keys()))
