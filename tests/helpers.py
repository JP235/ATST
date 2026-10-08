from pathlib import Path


FIXTURES_DIR = Path(__file__).parent / "fixtures"
MINIMAL_ATST_PATH = FIXTURES_DIR / "minimal.atst.txt"


def minimal_atst_text() -> str:
    return MINIMAL_ATST_PATH.read_text(encoding="utf-8")


def write_atst_text(directory: Path, text: str, name: str = "case.atst.tsv") -> Path:
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


def remove_block(text: str, block_name: str) -> str:
    start = text.index(f":::{block_name}_START")
    end_marker = f":::{block_name}_END"
    end = text.index(end_marker, start) + len(end_marker)
    return text[:start] + text[end:].lstrip("\n")


def block_text(text: str, block_name: str) -> str:
    start = text.index(f":::{block_name}_START")
    end_marker = f":::{block_name}_END"
    end = text.index(end_marker, start) + len(end_marker)
    return text[start:end]
