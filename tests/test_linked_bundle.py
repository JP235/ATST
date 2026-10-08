from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from zipfile import ZipFile

from ATST import (
    read_atst,
    write_atst,
    write_linked_atst_bundle,
    write_multi_readout_atst,
)


def share_only(atst, attribute):
    first, *others = atst.readouts.values()
    other_attribute = "assay" if attribute == "metadata" else "metadata"
    for index, readout in enumerate(others):
        getattr(readout, attribute).data = getattr(first, attribute).data.copy()
        getattr(readout, other_attribute).data["test_difference"] = str(index)


class LinkedBundleTests(TestCase):
    def _round_trip(self, source: str, *, multi: bool) -> list[str]:
        original = read_atst(source, multi_readouts=multi)
        with TemporaryDirectory() as directory:
            bundle = Path(directory) / "download.zip"
            write_linked_atst_bundle(original, bundle)
            with ZipFile(bundle) as archive:
                names = archive.namelist()
                archive.extractall(Path(directory) / "extracted")
            restored = read_atst(
                Path(directory) / "extracted" / "download.atst.txt",
                multi_readouts=multi,
            )
        self.assertEqual(type(restored), type(original))
        return names

    def test_single_readout_bundle_has_named_folders_and_reads_back(self):
        names = self._round_trip("examples/e1/example_1.atst.txt", multi=False)
        self.assertIn("download.atst.txt", names)
        self.assertTrue(any(name.startswith("metadata/") for name in names))
        self.assertTrue(any(name.startswith("assays/") for name in names))
        self.assertTrue(any(name.startswith("layouts/") for name in names))
        self.assertTrue(any(name.startswith("readings/") for name in names))
        self.assertTrue(any(name.startswith("entities/") for name in names))
        self.assertIn("entities/phages.tsv", names)

    def test_multi_readout_bundle_reads_back(self):
        names = self._round_trip("examples/e2/example_2.atst.txt", multi=True)
        self.assertGreaterEqual(sum(name.startswith("readings/") for name in names), 2)

    def test_multi_readout_bundle_shares_metadata_and_assay_independently(self):
        for attribute, folder, shared_file in (
            ("metadata", "metadata", "metadata/meta.tsv"),
            ("assay", "assays", "assays/assay.tsv"),
        ):
            with self.subTest(attribute=attribute), TemporaryDirectory() as directory:
                original = read_atst(
                    "examples/e2/example_2.atst.txt", multi_readouts=True
                )
                share_only(original, attribute)
                bundle = write_linked_atst_bundle(
                    original, Path(directory) / "download.zip"
                )
                with ZipFile(bundle) as archive:
                    names = archive.namelist()
                    text = archive.read("download.atst.txt").decode()

                self.assertEqual(
                    [name for name in names if name.startswith(f"{folder}/")],
                    [shared_file],
                )
                self.assertEqual(text.count(f"file={shared_file}"), len(original.readouts))


class LinkedDirectoryTests(TestCase):
    def test_single_readout_defaults_to_all_linkable_blocks(self):
        original = read_atst("examples/e1/example_1.atst.txt")
        with TemporaryDirectory() as directory:
            output = Path(directory) / "linked"
            container = write_atst(original, output, linked_files=True)
            expected = {
                "example_1.atst.txt",
                "metadata/metadata.tsv",
                "assays/assay.tsv",
                "entities/phages.tsv",
                "entities/isolates.tsv",
                "layouts/layout.tsv",
                "readings/readings.tsv",
            }
            actual = {
                str(path.relative_to(output))
                for path in output.rglob("*")
                if path.is_file()
            }
            restored = read_atst(container)

        self.assertEqual(actual, expected)
        self.assertEqual(restored.layout.data.shape, original.layout.data.shape)

    def test_single_readout_links_only_selected_blocks(self):
        original = read_atst("examples/e1/example_1.atst.txt")
        with TemporaryDirectory() as directory:
            output = Path(directory) / "linked"
            container = write_atst(
                original,
                output,
                linked_files=True,
                linked_blocks={"LAYOUT"},
            )
            text = container.read_text(encoding="utf-8")
            restored = read_atst(container)

            self.assertTrue((output / "layouts/layout.tsv").is_file())
            self.assertFalse((output / "metadata").exists())

        self.assertIn("<<<LAYOUT_READOUT file=layouts/layout.tsv", text)
        self.assertNotIn("<<<METADATA_READOUT", text)
        self.assertEqual(restored.readings.data.shape, original.readings.data.shape)

    def test_multi_readout_uses_readout_ids_in_layout_and_readings_filenames(self):
        original = read_atst(
            "examples/e2/example_2.atst.txt",
            multi_readouts=True,
        )
        with TemporaryDirectory() as directory:
            output = Path(directory) / "linked"
            container = write_multi_readout_atst(
                original,
                output,
                linked_files=True,
            )
            restored = read_atst(container, multi_readouts=True)
            expected = {
                f"{folder}/{prefix}_{readout_id}.tsv"
                for readout_id in original.readouts
                for folder, prefix in (
                    ("layouts", "layout"),
                    ("readings", "readings"),
                )
            }
            actual = {
                str(path.relative_to(output))
                for path in output.rglob("*.tsv")
            }

        self.assertTrue(expected <= actual)
        self.assertEqual(set(restored.readouts), set(original.readouts))

    def test_multi_readout_links_only_selected_blocks(self):
        original = read_atst(
            "examples/e2/example_2.atst.txt",
            multi_readouts=True,
        )
        with TemporaryDirectory() as directory:
            output = Path(directory) / "linked"
            container = write_multi_readout_atst(
                original,
                output,
                linked_files=True,
                linked_blocks={"METADATA", "READINGS"},
            )
            text = container.read_text(encoding="utf-8")
            restored = read_atst(container, multi_readouts=True)

            self.assertTrue(any((output / "metadata").glob("*.tsv")))
            self.assertTrue((output / "readings/readings_OD600.tsv").is_file())
            self.assertFalse((output / "assays").exists())
            self.assertFalse((output / "layouts").exists())

        self.assertIn("<<<METADATA_READOUT readout_id=GFP", text)
        self.assertNotIn("<<<ASSAY_READOUT", text)
        self.assertEqual(set(restored.readouts), set(original.readouts))

    def test_multi_readout_directory_shares_metadata_and_assay_independently(self):
        for attribute, folder, shared_file in (
            ("metadata", "metadata", "meta.tsv"),
            ("assay", "assays", "assay.tsv"),
        ):
            with self.subTest(attribute=attribute), TemporaryDirectory() as directory:
                original = read_atst(
                    "examples/e2/example_2.atst.txt", multi_readouts=True
                )
                share_only(original, attribute)
                output = Path(directory) / "linked"
                container = write_multi_readout_atst(
                    original, output, linked_files=True
                )
                text = container.read_text(encoding="utf-8")

                self.assertEqual(
                    list((output / folder).glob("*.tsv")),
                    [output / folder / shared_file],
                )
                self.assertEqual(
                    text.count(f"file={folder}/{shared_file}"), len(original.readouts)
                )

    def test_linked_block_names_are_case_sensitive(self):
        original = read_atst("examples/e1/example_1.atst.txt")
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "Unknown linked_blocks: metadata"):
                write_atst(
                    original,
                    directory,
                    linked_files=True,
                    linked_blocks={"metadata"},
                )

    def test_linked_blocks_requires_linked_output(self):
        original = read_atst("examples/e1/example_1.atst.txt")
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "requires linked_files=True"):
                write_atst(
                    original,
                    Path(directory) / "result.atst.txt",
                    linked_blocks={"LAYOUT"},
                )
