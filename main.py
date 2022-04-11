import ctypes
from ctypes import util as ctypes_util
import numpy as np
from enum import Enum
from datetime import datetime, timedelta
from time import sleep
import xarray as xr
from dataclasses import dataclass, field
from typing import List
from pandas import to_datetime, Timestamp
from os import name as os_name


@dataclass(frozen=True)
class SnapshotScheduleParameters:
    file_interval: timedelta = timedelta(seconds=300)
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
    
    def current_interval_start(self) -> Timestamp:
        return self.next_snapshot() - self.interval_length
    
    def current_interval_end(self) -> datetime:
        return self.next_snapshot()

    def current_file_time_end(self) -> Timestamp:
        time_now_offset = datetime.utcnow() + (self.file_interval / 2)
        return to_datetime(time_now_offset).round(self.file_interval)
    
    def n_interval_timesteps(self) -> int:
        final_snapshot = self.current_file_time_end()
        n_intervals = int((final_snapshot - datetime.utcnow() + self.interval_length) / self.repeat_any)
        return n_intervals
        
sschedule = SnapshotSchedule()

fps_expected = 30
if os_name == 'nt':
        #windows:
        lib = ctypes.CDLL("x64/libirimager.dll")
else:
        #linux:
        lib = ctypes.cdll.LoadLibrary(ctypes_util.find_library("irdirectsdk"))

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


res = -1
retries = 0
n_retries = 10

while res != 0:
    print('...')
    res = usb_init('config.xml')
    if retries > 10:
        raise ValueError("Could not initialise USB connection")
        terminate()
    retries += 1
    sleep(0.25)

sn = get_serial()

if sn == 0:
    raise ValueError("Invalid serial number")

set_shutter_mode(0)
trigger_shutter_flag()
sleep(0.5)

def write_file():
    width, height = get_thermal_image_size()
    n_interval_timesteps = sschedule.n_interval_timesteps()
    print(datetime.now())
    print(n_interval_timesteps)
    if n_interval_timesteps == 0:
        return None
    interval_length_s = sschedule.interval_length.total_seconds()
    file_end_raw = sschedule.current_file_time_end()
    file_name = str(file_end_raw).replace("-", "").replace(":", "").replace(" ", "")
    
    time_timeseries = np.empty(n_interval_timesteps)
    image_median_timeseries = np.empty((n_interval_timesteps, height, width), dtype=np.uint16)
    image_min_timeseries = np.empty((n_interval_timesteps, height, width), dtype=np.uint16)
    image_max_timeseries = np.empty((n_interval_timesteps, height, width), dtype=np.uint16)
    image_std_timeseries = np.empty((n_interval_timesteps, height, width), dtype=np.uint16)
    tbox_timeseries = np.empty(n_interval_timesteps, dtype=float)
    tchip_timeseries = np.empty(n_interval_timesteps, dtype=float)
    flagstate_timeseries = np.empty(n_interval_timesteps, dtype=int)
    counter_timeseries = np.empty(n_interval_timesteps, dtype=np.longlong)
    counterHW_timeseries = np.empty(n_interval_timesteps, dtype=np.longlong)
    fps_timeseries = np.empty(n_interval_timesteps, dtype=float)
    nsamples_timeseries = np.empty(n_interval_timesteps, dtype=int)
    n_images = int((interval_length_s * fps_expected) + 0.5)
    
    for j in range(0, n_interval_timesteps): 
        print(f'started n_interval_timestep {j} / {n_interval_timesteps} at {datetime.utcnow()}')
        interval_start_time = datetime.utcnow()
        images_raw = np.empty((n_images, height, width), dtype=np.uint16)
        for i in range(0, n_images):
            image, meta = get_thermal_image_metadata(width, height)
            images_raw[i, :, :] = image
            #print(f'got image {i} / {n_images} at {datetime.utcnow()}')
        interval_end_time = datetime.now()
        print(f'interval has timestamp {interval_end_time}')
        dtime = interval_end_time - interval_start_time
        fps = n_images / dtime.total_seconds()
        image_median_timeseries[j, :, :] = np.median(images_raw, axis=0)
        image_min_timeseries[j, :, :] = np.min(images_raw, axis=0)
        image_max_timeseries[j, :, :] = np.max(images_raw, axis=0)
        image_std_timeseries[j, :, :] = (np.std((images_raw - 1000) / 10, axis=0) * 10) + 1000
        time_timeseries[j] = interval_end_time.timestamp()
        tbox_timeseries[j] = meta.tempBox
        tchip_timeseries[j] = meta.tempChip
        flagstate_timeseries[j] = meta.flagState
        counter_timeseries[j] = meta.counter
        counterHW_timeseries[j] = meta.counterHW
        fps_timeseries[j] = fps
        nsamples_timeseries[j] = n_images
        print(j)
        print(n_interval_timesteps)
        if j != (n_interval_timesteps - 1):
            next_interval_time = interval_start_time + sschedule.repeat_any
            current_time = datetime.utcnow()
            wait_time_until_next_interval_s = (next_interval_time - 
                                               current_time).total_seconds()
            print(f'Time until next interval: {wait_time_until_next_interval_s}')
            if wait_time_until_next_interval_s < 0:
                print("Next interval start time missed. Slow scanning down.")
                wait_time_until_next_interval_s = 0
            sleep(wait_time_until_next_interval_s)
        else:
            d1 = datetime.utcnow()
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
            ds.to_netcdf(f"OUT/{file_name}.nc", 
                         encoding={
                             'time': {'dtype': 'i4'}, 
                             't_b_median': {'zlib': True, "complevel": 7},
                             't_b_min': {'zlib': True, "complevel": 7},
                             't_b_max': {'zlib': True, "complevel": 7},
                             't_b_std': {'zlib': True, "complevel": 7},
                             'nsamples': {'zlib': True, "complevel": 7},
                             })

while True:
    write_file()
