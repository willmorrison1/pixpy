from datetime import datetime, timedelta
from dataclasses import dataclass
from pandas import to_datetime, Timestamp
import ctypes as ctps
from ctypes import util as ctypes_util
from os import name as os_name
from time import sleep
import numpy as np
from enum import Enum
# todo: reference original repo that some of these functions came from

if os_name == 'nt':
    # windows
    lib = ctps.CDLL('x64/libirimager.dll')
else:
    # linux
    lib = ctps.cdll.LoadLibrary(ctypes_util.find_library('irdirectsdk'))
        
@dataclass(frozen=True) # todo: docstr
class SnapshotScheduleParameters:
    file_interval_length: timedelta = timedelta(seconds=300)
    sample_length: timedelta = timedelta(seconds=5)
    repeat_any: timedelta = timedelta(seconds=60)
    
    if repeat_any <= sample_length:
        raise ValueError('repeat_any <= sample_length')
    if file_interval_length <= sample_length:
        raise ValueError('file_interval_length <= sample_length')
    if file_interval_length <= repeat_any:
        raise ValueError("file_interval_length <= repeat_any")
    
class SnapshotSchedule(SnapshotScheduleParameters):
    def next_snapshot(self) -> Timestamp:
        time_now_offset = datetime.utcnow() + (self.repeat_any / 2)
        return to_datetime(time_now_offset).round(self.repeat_any)
    
    def current_sample_start(self) -> Timestamp:
        return self.next_snapshot() - self.sample_length
    
    def current_sample_end(self) -> datetime:
        return self.next_snapshot()

    def current_file_time_end(self) -> Timestamp:
        time_now_offset = datetime.utcnow() + (self.file_sample / 2)
        return to_datetime(time_now_offset).round(self.file_interval)
    
    def sample_timesteps_remaining(self) -> int:
        final_snapshot = self.current_file_time_end()
        n_samples = int((final_snapshot - datetime.utcnow() + \
                         self.sample_length) / self.repeat_any)
        return n_samples

# todo: make min_trigger_interval the only settable parameter
@dataclass()
class Shutter:
    last_trigger_result: int = None
    last_trigger_time: int = datetime.utcnow() - timedelta(days=365)
    min_trigger_interval: timedelta = timedelta(seconds=15)
    cycle_time: timedelta = None
    triggers: int = 0
    
    def trigger(self):
        trigger_start_time = datetime.utcnow()
        if (trigger_start_time - self.last_trigger_time) > self.min_trigger_interval:
            self.last_trigger_result = trigger_shutter_flag()
            trigger_end_time = datetime.utcnow()
            self.last_trigger_time = trigger_end_time
            self.cycle_time = trigger_end_time - trigger_start_time
            self.triggers += 1
            
class ShutterMode(Enum):
    MANUAL = 0
    AUTO = 1

class EvoIRFrameMetadata(ctps.Structure):
    _fields_ = [
        ("counter", ctps.c_uint),
        ("counterHW", ctps.c_uint),
        ("timestamp", ctps.c_longlong),
        ("timestampMedia", ctps.c_longlong),
        ("flagState", ctps.c_uint),
        ("tempChip", ctps.c_float),
        ("tempFlag", ctps.c_float),
        ("tempBox", ctps.c_float),
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
    width = ctps.c_int()
    height = ctps.c_int()
    _ = lib.evo_irimager_get_thermal_image_size(ctps.byref(width), 
                                                ctps.byref(height))
    return width.value, height.value

def get_palette_image_size() -> (int, int):
    width = ctps.c_int()
    height = ctps.c_int()
    _ = lib.evo_irimager_get_palette_image_size(ctps.byref(width), 
                                                ctps.byref(height))
    return width.value, height.value

def get_thermal_image(width: int, height: int) -> np.ndarray:
    w = ctps.byref(ctps.c_int(width))
    h = ctps.byref(ctps.c_int(height))
    thermalData = np.empty((height, width), dtype=np.uint16)
    thermalDataPointer = thermalData.ctps.data_as(ctps.POINTER(ctps.c_ushort))
    _ = lib.evo_irimager_get_thermal_image(w, h, thermalDataPointer)
    return thermalData

def get_palette_image(width: int, height: int) -> np.ndarray:
    w = ctps.byref(ctps.c_int(width))
    h = ctps.byref(ctps.c_int(height))
    paletteData = np.empty((height, width, 3), dtype=np.uint8)
    paletteDataPointer = paletteData.ctps.data_as(ctps.POINTER(ctps.c_ubyte))
    retVal = -1
    while retVal != 0:
        retVal = lib.evo_irimager_get_palette_image(w, h, paletteDataPointer)
    return paletteData

def terminate() -> int:
    return lib.evo_irimager_terminate()

def get_serial() -> int:
    s = ctps.c_int()
    _ = lib.evo_irimager_get_serial(ctps.byref(s))
    return s.value
    
def set_shutter_mode(shutterMode: ShutterMode) -> int:
    return lib.evo_irimager_set_shutter_mode(shutterMode)

def trigger_shutter_flag() -> int:
    return lib.evo_irimager_trigger_shutter_flag(None)

def set_temperature_range(min: int, max: int) -> int:
    return lib.evo_irimager_set_temperature_range(min, max)

def get_thermal_image_metadata(width: int, height: int) -> (np.ndarray, 
                                                            EvoIRFrameMetadata):
    w = ctps.byref(ctps.c_int(width))
    h = ctps.byref(ctps.c_int(height))
    data = np.empty((height, width), dtype=np.uint16)
    data_pointer = data.ctps.data_as(ctps.POINTER(ctps.c_ushort))
    meta = EvoIRFrameMetadata()
    meta_pointer = ctps.pointer(meta)
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