from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from zipfile import ZipFile

from streamlit.testing.v1 import AppTest

from ATST import MultiReadoutATST, read_atst, write_linked_atst_bundle
from streamlit_app.generator.inspector import read_uploaded_atst


class InspectorUploadTests(TestCase):
    def test_inspector_accepts_linked_zip(self):
        source = read_atst("examples/e2/example_2.atst.txt", multi_readouts=True)

        with TemporaryDirectory() as directory:
            bundle = write_linked_atst_bundle(source, Path(directory) / "bundle.zip")
            upload = SimpleNamespace(name="bundle.zip", getvalue=bundle.read_bytes)
            inspected = read_uploaded_atst(upload)

        self.assertIsInstance(inspected, MultiReadoutATST)
        self.assertEqual(set(inspected.readouts), set(source.readouts))

    def test_inspector_uses_first_container_one_folder_deep(self):
        source = Path("tests/fixtures/minimal.atst.txt").read_bytes()
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("first/example.atst.txt", source)
            archive.writestr("second/ignored.atst.txt", source)

        inspected = read_uploaded_atst(
            SimpleNamespace(name="nested.zip", getvalue=buffer.getvalue)
        )

        self.assertEqual(inspected.study.data["study_id"], "ATST_MINIMAL")

    def test_inspector_rejects_multiple_root_containers(self):
        source = Path("tests/fixtures/minimal.atst.txt").read_bytes()
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("first.atst.txt", source)
            archive.writestr("second.atst.txt", source)

        with self.assertRaisesRegex(ValueError, "exactly one root ATST file"):
            read_uploaded_atst(
                SimpleNamespace(name="multiple.zip", getvalue=buffer.getvalue)
            )

    def test_inspector_rejects_unsafe_zip_path(self):
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("../example.atst.txt", b"unsafe")

        with self.assertRaisesRegex(ValueError, "unsafe path"):
            read_uploaded_atst(
                SimpleNamespace(name="unsafe.zip", getvalue=buffer.getvalue)
            )

    def test_inspector_uploader_allows_zip(self):
        app = AppTest.from_file("src/streamlit_app/pages/1_Inspect_File.py").run(
            timeout=20
        )

        self.assertEqual(
            app.get("file_uploader")[0].allowed_type, [".txt", ".tsv", ".zip"]
        )
