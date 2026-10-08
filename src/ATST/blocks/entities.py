from dataclasses import dataclass, field

from ATST.blocks import ENTITIES
from ATST.blocks.base_classes import WideTable


@dataclass
class EntityTable(WideTable):
    """Named entity lookup table with a primary-key column."""

    table_name: str = ""
    pk: str = ""


@dataclass
class Entities:
    """Collection of named entity tables stored in an ATST `ENTITIES` block."""

    name = ENTITIES
    tables: dict[str, EntityTable] = field(default_factory=dict)

    
    @property
    def names(self):
        return self.tables.keys()
    
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

    def __str__(self) -> str:
        if not self.tables:
            return "Entities()"

        return "\n\n".join(
            f"{table.table_name} (pk={table.pk})\n{table.data}"
            for table in self.tables.values()
        )

    def __repr__(self) -> str:
        return str(self)
