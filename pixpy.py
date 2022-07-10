from datetime import datetime, timedelta
from dataclasses import dataclass
from pandas import to_datetime, Timestamp
import ctypes
from ctypes import util as ctypes_util
from os import name as os_name
from time import sleep
import numpy as np
from enum import Enum
# todo: reference original repo that some of these functions came from

if os_name == 'nt':
    # windows
    lib = ctypes.CDLL('x64/libirimager.dll')
else:
    # linux
    lib = ctypes.cdll.LoadLibrary(ctypes_util.find_library('irdirectsdk'))


@dataclass(frozen=True)  # todo: docstr
class SnapshotScheduleParameters:
    file_interval: timedelta = timedelta(seconds=300)
    sample_interval: timedelta = timedelta(seconds=5)
    sample_repetition: timedelta = timedelta(seconds=60)

    if sample_repetition <= sample_interval:
        raise ValueError('sample_repetition <= sample_interval')
    if file_interval <= sample_interval:
        raise ValueError('file_interval <= sample_interval')
    if file_interval <= sample_repetition:
        raise ValueError("file_interval <= sample_repetition")


class SnapshotSchedule(SnapshotScheduleParameters):
    def next_snapshot(self) -> Timestamp:
        time_now_offset = datetime.utcnow() + (self.sample_repetition / 2)
        return to_datetime(time_now_offset).round(self.sample_repetition)

    def current_sample_start(self) -> Timestamp:
        return self.next_snapshot() - self.sample_interval

    def current_sample_end(self) -> datetime:
        return self.next_snapshot()

    def current_file_time_end(self) -> Timestamp:
        time_now_offset = datetime.utcnow() + (self.file_interval / 2)
        return to_datetime(time_now_offset).round(self.file_interval)

    def sample_timesteps_remaining(self) -> int:
        final_snapshot = self.current_file_time_end()
        n_samples = int((final_snapshot - datetime.utcnow() +
                         self.sample_interval) / self.sample_repetition)
        return n_samples


# todo: make min_trigger_interval the only settable parameter
@dataclass()
class Shutter:
    _last_trigger_result: int = None
    _last_trigger_time: int = datetime.utcnow() - timedelta(days=365)
    min_trigger_interval: timedelta = timedelta(seconds=15)
    _cycle_time: timedelta = None
    _triggers: int = 0

    def trigger(self, sleep=True):
        trigger_start_time = datetime.utcnow()
        if (trigger_start_time - self._last_trigger_time) > self.min_trigger_interval:
            self._last_trigger_result = trigger_shutter_flag()
            trigger_end_time = datetime.utcnow()
            self._last_trigger_time = trigger_end_time
            self.cycle_cycle_time_time = trigger_end_time - trigger_start_time
            self._triggers += 1
            return 0
        else:
            return -1


class ShutterMode(Enum):
    MANUAL = 0
    AUTO = 1


class EvoIRFrameMetadata(ctypes.Structure):
    _fields_ = [
        ("counter", ctypes.c_uint),
        ("counterHW", ctypes.c_uint),
        ("timestamp", ctypes.c_longlong),
        ("timestampMedia", ctypes.c_longlong),
        ("flagState", ctypes.c_uint),
        ("tempChip", ctypes.c_float),
        ("tempFlag", ctypes.c_float),
        ("tempBox", ctypes.c_float),
        ]

    def __repr__(self):
        out = (
            f'counter:       {self.counter}\n'
            f'counterHW:     {self.counterHW}\n'
            f'timestamp:     {self.timestamp}\n'
            f'timestampMedia:{self.timestampMedia}\n'
            f'flagState:     {self.flagState}\n'
            f'tempChip:      {self.tempChip}\n'
            f'tempFlag:      {self.tempFlag}\n'
            f'tempBox:       {self.tempBox}\n'
        )
        return out


def usb_init(xml_config: str, formats_def: str = None,
             log_file: str = None) -> int:
    return lib.evo_irimager_usb_init(
        xml_config.encode(),
        None if formats_def is None else formats_def.encode(),
        None if log_file is None else log_file.encode())


def get_thermal_image_size() -> (int, int):
    width = ctypes.c_int()
    height = ctypes.c_int()
    _ = lib.evo_irimager_get_thermal_image_size(ctypes.byref(width),
                                                ctypes.byref(height))
    return width.value, height.value


def get_palette_image_size() -> (int, int):
    width = ctypes.c_int()
    height = ctypes.c_int()
    _ = lib.evo_irimager_get_palette_image_size(ctypes.byref(width),
                                                ctypes.byref(height))
    return width.value, height.value


def get_thermal_image(width: int, height: int) -> np.ndarray:
    w = ctypes.byref(ctypes.c_int(width))
    h = ctypes.byref(ctypes.c_int(height))
    thermalData = np.empty((height, width), dtype=np.uint16)
    thermalDataPointer = thermalData.ctypes.data_as(
            ctypes.POINTER(ctypes.c_ushort))
    _ = lib.evo_irimager_get_thermal_image(w, h, thermalDataPointer)
    return thermalData


def get_palette_image(width: int, height: int) -> np.ndarray:
    w = ctypes.byref(ctypes.c_int(width))
    h = ctypes.byref(ctypes.c_int(height))
    paletteData = np.empty((height, width, 3), dtype=np.uint8)
    paletteDataPointer = paletteData.ctypes.data_as(
            ctypes.POINTER(ctypes.c_ubyte))
    retVal = -1
    while retVal != 0:
        retVal = lib.evo_irimager_get_palette_image(w, h, paletteDataPointer)
    return paletteData


def terminate() -> int:
    return lib.evo_irimager_terminate()


def get_serial() -> int:
    s = ctypes.c_int()
    _ = lib.evo_irimager_get_serial(ctypes.byref(s))
    return s.value


def set_shutter_mode(shutterMode: ShutterMode) -> int:
    return lib.evo_irimager_set_shutter_mode(shutterMode)


def trigger_shutter_flag() -> int:
    return lib.evo_irimager_trigger_shutter_flag(None)


def set_temperature_range(min: int, max: int) -> int:
    return lib.evo_irimager_set_temperature_range(min, max)


def get_thermal_image_metadata(
        width: int, height: int) -> (np.ndarray, EvoIRFrameMetadata):
    w = ctypes.byref(ctypes.c_int(width))
    h = ctypes.byref(ctypes.c_int(height))
    data = np.empty((height, width), dtype=np.uint16)
    data_pointer = data.ctypes.data_as(ctypes.POINTER(ctypes.c_ushort))
    meta = EvoIRFrameMetadata()
    meta_pointer = ctypes.pointer(meta)
    _ = lib.evo_irimager_get_thermal_image_metadata(
            w, h, data_pointer, meta_pointer)
    return data, meta


def usb_init_retry(config_file: str, n_retries: int = 10,
                   retry_time: float = 0.25):
    res = -1
    retries = 0
    while res != 0:
        print('...')
        res = usb_init(config_file)
        if retries > n_retries:
            raise ValueError("Could not initialise USB connection")
            terminate()
        retries += 1
        sleep(retry_time)
