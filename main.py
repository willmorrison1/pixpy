from datetime import datetime, timedelta
from time import sleep
import xarray as xr
import pixpy 
import numpy as np
import xml.etree.ElementTree as ET
import argparse
from os import path

parser = argparse.ArgumentParser()
parser.add_argument('--config_file', type=str, help='The config.xml file', 
                    default='config.xml')
parser.add_argument('--file_interval', type=int, 
                    help='The time interval for each file (seconds)', default=300)
parser.add_argument('--sample_length', type=int, 
                    help='The lenght of time for a sample (seconds)', default=5)
parser.add_argument('--repeat_any', type=int, 
                    help='The length of time between samples (seconds)', default=60)
parser.add_argument('--output_directory', type=str, 
                    help='The name of the output directory', default='OUT')
args = parser.parse_args()

sschedule = pixpy.SnapshotSchedule(
    file_sample=timedelta(seconds=args.file_interval),
    sample_length=timedelta(seconds=args.sample_length),
    repeat_any=timedelta(args.repeat_any),
    )

tree = ET.parse(args.config_file)

fps_expected = int(tree.getroot().find('framerate').text)
sn_expected = int(tree.getroot().find('serial').text)

shutter_delay = 0.1 # assumed
skip_frames_after_shutter_delay_s = (2 / fps_expected) # number of frames to skip after shutter
pre_sample_delay_s = shutter_delay + skip_frames_after_shutter_delay_s

def write_file():
    width, height = pixpy.get_thermal_image_size()
    interval_timesteps_remaining = sschedule.interval_timesteps_remaining()
    print(datetime.utcnow())
    print(interval_timesteps_remaining)
    interval_length_s = sschedule.interval_length.total_seconds()
    file_end_raw = sschedule.current_file_time_end()
    file_name = str(file_end_raw).replace("-", "").replace(":", "").replace(" ", "")
    
    time_timeseries = np.empty(interval_timesteps_remaining)
    image_median_timeseries = np.empty((interval_timesteps_remaining, height, width), dtype=np.uint16)
    image_min_timeseries = np.empty((interval_timesteps_remaining, height, width), dtype=np.uint16)
    image_max_timeseries = np.empty((interval_timesteps_remaining, height, width), dtype=np.uint16)
    image_std_timeseries = np.empty((interval_timesteps_remaining, height, width), dtype=np.uint16)
    tbox_timeseries = np.empty(interval_timesteps_remaining, dtype=float)
    tchip_timeseries = np.empty(interval_timesteps_remaining, dtype=float)
    flagstate_timeseries = np.empty(interval_timesteps_remaining, dtype=int)
    counter_timeseries = np.empty(interval_timesteps_remaining, dtype=np.longlong)
    counterHW_timeseries = np.empty(interval_timesteps_remaining, dtype=np.longlong)
    fps_timeseries = np.empty(interval_timesteps_remaining, dtype=float)
    nsamples_timeseries = np.empty(interval_timesteps_remaining, dtype=int)
    n_images = int((interval_length_s * fps_expected) + 0.5)
    time_until_next_interval = sschedule.current_interval_start() - datetime.utcnow()
    while time_until_next_interval.total_seconds() < 0:
        time_until_next_interval = sschedule.current_interval_start() - datetime.utcnow()
    sleep(time_until_next_interval.total_seconds())
    for j in range(0, interval_timesteps_remaining):
        shut.trigger()
        sleep(skip_frames_after_shutter_delay_s)
        print(f'started n_interval_timestep {j + 1} / {interval_timesteps_remaining} at {datetime.utcnow()}')
        interval_start_time = datetime.utcnow()
        images_raw = np.empty((n_images, height, width), dtype=np.uint16)
        for i in range(0, n_images):
            image, meta = pixpy.get_thermal_image_metadata(width, height)
            images_raw[i, :, :] = image
            #print(f'got image {i} / {n_images} at {datetime.utcnow()}')
        interval_end_time = datetime.utcnow()
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
        if j != (interval_timesteps_remaining - 1):
            next_interval_time = interval_start_time + sschedule.repeat_any
            current_time = datetime.utcnow()
            wait_time_until_next_interval_s = (next_interval_time - 
                                               current_time).total_seconds()
            print(f'Time until next interval: {wait_time_until_next_interval_s}')
            if wait_time_until_next_interval_s < 0:
                print("Next interval start time missed. Slow the sampling rate and/or fps.")
                wait_time_until_next_interval_s = 0
            sleep(wait_time_until_next_interval_s - pre_sample_delay_s)
        else:
            x = np.arange(0, 160)
            y = np.flip(np.arange(0, 120))
            
            ds = xr.Dataset(
                data_vars=dict(
                    t_b_median=(["time", "y", "x"], image_median_timeseries),
                    t_b_min=(["time", "y", "x"], image_min_timeseries),
                    t_b_max=(["time", "y", "x"], image_max_timeseries),
                    t_b_std=(["time", "y", "x"], image_std_timeseries),
                    t_b_snapshot=(["time", "y", "x"], image),
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
            ds.to_netcdf(path.join(args.output_directory, f'{file_name}.nc'), 
                         encoding={
                             'time': {'dtype': 'i4'}, 
                             't_b_median': {'zlib': True, "complevel": 5},
                             't_b_min': {'zlib': True, "complevel": 5},
                             't_b_max': {'zlib': True, "complevel": 5},
                             't_b_std': {'zlib': True, "complevel": 5},
                             't_b_snapshot': {'zlib': True, "complevel": 5},
                             'nsamples': {'zlib': True, "complevel": 5},
                             })

pixpy.usb_init_retry(args.config_file)

sn = pixpy.get_serial()
shut = pixpy.Shutter()

if sn == 0:
    raise ValueError("Invalid serial number")
    
if sn_expected != sn:
    raise ValueError(f'sn of attached camera is different to sn in {args.config_file}')

pixpy.set_shutter_mode(0)
shut.trigger()
sleep(0.25)
# todo - wrap in try catch and redo usb_init as appropriate
while True:
    write_file()
