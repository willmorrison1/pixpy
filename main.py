import ctypes
import numpy as np
from matplotlib import pyplot as plt
from enum import Enum
from datetime import datetime
import time

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

def get_serial():
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
sample_interval_s = 5
fps_expected = 40

if res != -1:
    raise ValueError("Could not initialise USB connection")
time.sleep(1)
print(get_serial())
set_shutter_mode(1)
trigger_shutter_flag()
time.sleep(1)
width, height = get_thermal_image_size()
n_images = sample_interval_s * fps_expected
raw_data = np.empty((height, width, n_images), dtype=np.uint16)
image, meta = get_thermal_image_metadata(width, height)
start = datetime.now()
for i in range(0, n_images):
    image = get_thermal_image(width, height)
    raw_data[:, :, i] = image
end = datetime.now()
dtime = end - start
print(dtime)
fps_actual = n_images / dtime.total_seconds()
print(fps_actual)

raw_data = (raw_data - 1000) / 10
fig, ax = plt.subplots()
shw = ax.imshow(np.std(raw_data, axis=2))
bar = plt.colorbar(shw)
plt.show()

fig, ax = plt.subplots()
shw = ax.imshow(np.mean(raw_data, axis=2))
bar = plt.colorbar(shw)
plt.show()

fig, ax = plt.subplots()
shw = ax.imshow(np.max(raw_data, axis=2) - np.min(raw_data, axis=2))
bar = plt.colorbar(shw)
plt.show()

# res = terminate()
# if res != 0:
#     raise ValueError("USB connection did not terminate as expected")