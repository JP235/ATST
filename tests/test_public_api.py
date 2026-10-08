import unittest

import ATST
from ATST import device_readers
from ATST.ATSTFile import (
    ATSTFile,
    MultiReadoutATST,
    read_atst,
    validate_atst,
    write_atst,
    write_long_table,
    write_multi_readout_atst,
    write_linked_atst_bundle,
    write_wide_table,
)


class PublicAPITests(unittest.TestCase):
    def test_atstfile_api_is_available_from_package_root(self):
        expected = {
            "ATSTFile": ATSTFile,
            "MultiReadoutATST": MultiReadoutATST,
            "read_atst": read_atst,
            "validate_atst": validate_atst,
            "write_atst": write_atst,
            "write_long_table": write_long_table,
            "write_multi_readout_atst": write_multi_readout_atst,
            "write_linked_atst_bundle": write_linked_atst_bundle,
            "write_wide_table": write_wide_table,
        }
        expected.update(
            {
                name: getattr(device_readers, name)
                for name in device_readers.__all__
            }
        )

        self.assertEqual(set(ATST.__all__), set(expected))
        for name, value in expected.items():
            self.assertIs(getattr(ATST, name), value)


if __name__ == "__main__":
    unittest.main()
