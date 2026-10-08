from ATST.device_readers.protocol import DeviceOutput, DeviceReader
from ATST.device_readers.clariostar import (
    ClariostarOutput,
    ClariostarParseError,
    ClariostarReader,
    parse_clariostar_output,
)
from ATST.device_readers.logphase600 import (
    LogPhaseParseError,
    LogPhase600Output,
    LogPhase600Reader,
    parse_logphase600_output,
)
from ATST.device_readers.tecan import (
    TecanOutput,
    TecanParseError,
    TecanReader,
    parse_tecan_output,
)


DEVICE_READERS: dict[str, DeviceReader] = {
    "LogPhase600": LogPhase600Reader(),
    "SparkControl": TecanReader(),
    "CLARIOstar": ClariostarReader(),
}

__all__ = [
    "DeviceOutput",
    "DeviceReader",
    "DEVICE_READERS",
    "ClariostarOutput",
    "ClariostarParseError",
    "ClariostarReader",
    "LogPhaseParseError",
    "LogPhase600Output",
    "LogPhase600Reader",
    "TecanOutput",
    "TecanParseError",
    "TecanReader",
    "parse_clariostar_output",
    "parse_logphase600_output",
    "parse_tecan_output",
]
