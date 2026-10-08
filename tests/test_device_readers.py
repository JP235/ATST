from pathlib import Path
import unittest

from ATST import (
    DEVICE_READERS,
    DeviceOutput,
    DeviceReader,
)


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class DeviceReaderProtocolTests(unittest.TestCase):
    def test_all_registered_readers_follow_protocol_and_read_device_output(self):
        fixtures = {
            "LogPhase600": EXAMPLES
            / "e4/raw_outputs/simulated_logphase_output.txt",
            "SparkControl": EXAMPLES
            / "e3/raw_outputs/simulated_tecan_100rpm_output.xlsx",
            "CLARIOstar": EXAMPLES
            / "e2/raw_outputs/simulated_clariostar_od600_output.csv",
        }

        self.assertEqual(set(DEVICE_READERS), set(fixtures))
        for device, path in fixtures.items():
            with self.subTest(device=device):
                reader = DEVICE_READERS[device]
                self.assertIsInstance(reader, DeviceReader)
                parsed = reader.read(path.read_bytes(), filename=path.name)
                self.assertIsInstance(parsed, DeviceOutput)
                self.assertFalse(parsed.readings.empty)


if __name__ == "__main__":
    unittest.main()
