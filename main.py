import ctypes
import numpy as np
from enum import Enum
from datetime import datetime, timedelta
from time import sleep
import xarray as xr
from dataclasses import dataclass, field
from typing import List
from pandas import to_datetime, Timestamp

@dataclass(frozen=True)
class SnapshotScheduleParameters:
    file_interval: timedelta = timedelta(minutes=1)
    timerange: (datetime, datetime) = (datetime.utcnow(), datetime.utcnow() + timedelta(days=365*10))
    interval_stats: List[str] = field(default_factory=list)
    interval_length: timedelta = timedelta(seconds=5)
    repeat_any: timedelta = timedelta(seconds=10)
    #repeat_any_offset: timedelta = timedelta(seconds=0) # todo
    
    if repeat_any < interval_length:
        raise ValueError("repeat_any < interval_length")
    if timerange[1] < timerange[0]:
        raise ValueError("end time is before start time")
    #todo: further validation
    
class SnapshotSchedule(SnapshotScheduleParameters):
    def next_snapshot(self) -> Timestamp:
        time_now_offset = datetime.utcnow() + (self.repeat_any / 2)
        return to_datetime(time_now_offset).round(self.repeat_any)
    
    def next_interval_start(self) -> Timestamp:
        time_now_offset = datetime.utcnow() + (self.repeat_any / 2) + self.interval_length
        return to_datetime(time_now_offset).round(self.repeat_any) - self.interval_length
    
    def next_interval_end(self) -> datetime:
        return self.next_interval_start() + self.interval_length
    
    def current_file_time_end(self) -> Timestamp:
        time_now_offset = datetime.utcnow() + (self.file_interval / 2)
        return to_datetime(time_now_offset).round(self.file_interval)
    
    def n_interval_timesteps(self) -> int:
        next_snapshot = self.next_snapshot()
        final_snapshot = self.current_file_time_end()
        return int((final_snapshot - next_snapshot + self.repeat_any) / self.repeat_any)
        
sschedule = SnapshotSchedule()

fps_expected = 40

lib = ctypes.WinDLL("x64/libirimager")

def usb_init(xml_config: str, formats_def: str = None, log_file: str = None) -> int:
    return lib.evo_irimager_usb_init(xml_config.encode(), None if formats_def is None else formats_def.encode(), None if log_file is None else log_file.encode())

def get_thermal_image_size() -> (int, int):
    width = ctypes.c_int()
    height = ctypes.c_int()
    _ = lib.evo_irimager_get_thermal_image_size(ctypes.byref(width), ctypes.byref(height))
    return width.value, height.value

def get_palette_image_size() -> (int, int):
    width = ctypes.c_int()
    height = ctypes.c_int()
    _ = lib.evo_irimager_get_palette_image_size(ctypes.byref(width), ctypes.byref(height))
    return width.value, height.value

def get_thermal_image(width: int, height: int) -> np.ndarray:
    w = ctypes.byref(ctypes.c_int(width))
    h = ctypes.byref(ctypes.c_int(height))
    thermalData = np.empty((height, width), dtype=np.uint16)
    thermalDataPointer = thermalData.ctypes.data_as(ctypes.POINTER(ctypes.c_ushort))
    _ = lib.evo_irimager_get_thermal_image(w, h, thermalDataPointer)
    return thermalData

def get_palette_image(width: int, height: int) -> np.ndarray:
    w = ctypes.byref(ctypes.c_int(width))
    h = ctypes.byref(ctypes.c_int(height))
    paletteData = np.empty((height, width, 3), dtype=np.uint8)
    paletteDataPointer = paletteData.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))
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
    
class ShutterMode(Enum):
    MANUAL = 0
    AUTO = 1

class ShutterStatus(Enum):
    CLOSED = 1
    OPEN = 0
    #OPENING = n #todo

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
         
def set_shutter_mode(shutterMode: ShutterMode) -> int:
    return lib.evo_irimager_set_shutter_mode(shutterMode)

def trigger_shutter_flag() -> int:
    return lib.evo_irimager_trigger_shutter_flag(None)

def set_temperature_range(min: int, max: int) -> int:
    return lib.evo_irimager_set_temperature_range(min, max)

def get_thermal_image_metadata(width: int, height: int) -> (np.ndarray, EvoIRFrameMetadata):
    w = ctypes.byref(ctypes.c_int(width))
    h = ctypes.byref(ctypes.c_int(height))
    data = np.empty((height, width), dtype=np.uint16)
    data_pointer = data.ctypes.data_as(ctypes.POINTER(ctypes.c_ushort))
    meta = EvoIRFrameMetadata()
    meta_pointer = ctypes.pointer(meta)
    _ = lib.evo_irimager_get_thermal_image_metadata(w, h, data_pointer, meta_pointer)
    return data, meta

res = usb_init('config.xml')

if res != -1:
    raise ValueError("Could not initialise USB connection")

sleep(0.5)
sn = get_serial()
set_shutter_mode(0)
trigger_shutter_flag()
sleep(0.5)


def write_file():
    width, height = get_thermal_image_size()
    n_samples = sschedule.n_interval_timesteps()
    sample_interval_s = sschedule.interval_length.total_seconds()
    file_end_raw = sschedule.current_file_time_end()
    file_name = str(file_end_raw).replace("-", "").replace(":", "").replace(" ", "")
    
    time_timeseries = np.empty(n_samples)
    image_median_timeseries = np.empty((n_samples, height, width), dtype=np.uint16)
    image_min_timeseries = np.empty((n_samples, height, width), dtype=np.uint16)
    image_max_timeseries = np.empty((n_samples, height, width), dtype=np.uint16)
    image_std_timeseries = np.empty((n_samples, height, width), dtype=np.uint16)
    tbox_timeseries = np.empty(n_samples, dtype=float)
    tchip_timeseries = np.empty(n_samples, dtype=float)
    flagstate_timeseries = np.empty(n_samples, dtype=int)
    counter_timeseries = np.empty(n_samples, dtype=np.longlong)
    counterHW_timeseries = np.empty(n_samples, dtype=np.longlong)
    fps_timeseries = np.empty(n_samples, dtype=float)
    nsamples_timeseries = np.empty(n_samples, dtype=int)
    
    print(str(n_samples))
    while datetime.utcnow() < (file_end_raw - sschedule.interval_length):
        wait_time = sschedule.next_interval_start() - datetime.utcnow()
        sleep(wait_time.total_seconds())
        
        for j in range(0, n_samples):
            n_images = int((sample_interval_s * fps_expected) + 0.5)
            images_raw = np.empty((n_images, height, width), dtype=np.uint16)
            start = datetime.now()
            for i in range(0, n_images):
                image = get_thermal_image(width, height)
                images_raw[i, :, :] = image
            image, meta = get_thermal_image_metadata(width, height)
            end = datetime.now()
            dtime = end - start
            fps = n_images / dtime.total_seconds()
            image_median_timeseries[j, :, :] = np.median(images_raw, axis=0)
            image_min_timeseries[j, :, :] = np.min(images_raw, axis=0)
            image_max_timeseries[j, :, :] = np.max(images_raw, axis=0)
            image_std_timeseries[j, :, :] = (np.std((images_raw - 1000) / 10, axis=0) * 10) + 1000
            time_timeseries[j] = end.timestamp()
            tbox_timeseries[j] = meta.tempBox
            tchip_timeseries[j] = meta.tempChip
            flagstate_timeseries[j] = meta.flagState
            counter_timeseries[j] = meta.counter
            counterHW_timeseries[j] = meta.counterHW
            fps_timeseries[j] = fps
            nsamples_timeseries[j] = n_images
            
        x = np.arange(0, 160)
        y = np.flip(np.arange(0, 120))
        
        ds = xr.Dataset(
            data_vars=dict(
                t_b_median=(["time", "y", "x"], image_median_timeseries),
                t_b_min=(["time", "y", "x"], image_min_timeseries),
                t_b_max=(["time", "y", "x"], image_max_timeseries),
                t_b_std=(["time", "y", "x"], image_std_timeseries),
                t_box=(["time"], tbox_timeseries),
                t_chip=(["time"], tchip_timeseries),
                flag_state=(["time"], flagstate_timeseries),
                counter=(["time"], counter_timeseries),
                counterHW=(["time"], counterHW_timeseries),
                fps=(["time"], fps_timeseries),
                nsamples=(["time"], nsamples_timeseries),
            ),
            coords=dict(
                x=x,
                y=y,        
                time=[datetime.utcfromtimestamp(i) for i in time_timeseries],
            ),
            attrs=dict(description="pixpy",
                       serial=sn),
        )
        
        ds.to_netcdf(f"C:/Users/willm/Desktop/{file_name}.nc", 
                     encoding={
                         'time': {'dtype': 'i4'}, 
                         't_b_median': {'zlib': True, "complevel": 7},
                         't_b_min': {'zlib': True, "complevel": 7},
                         't_b_max': {'zlib': True, "complevel": 7},
                         't_b_std': {'zlib': True, "complevel": 7},
                         'nsamples': {'zlib': True, "complevel": 7},
                         })

while True:
    print(datetime.utcnow())
    next_run = sschedule.next_interval_start()
    time_until_next_run = next_run - datetime.utcnow()
    if time_until_next_run < (sschedule.interval_length):
        sleep((time_until_next_run - (sschedule.interval_length / 2)).total_seconds())
        write_file()
    
