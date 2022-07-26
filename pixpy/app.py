from pixpy.args import args
from datetime import datetime as dt, timedelta
from time import sleep
import xarray as xr
import pixpy
import numpy as np
import xml.etree.ElementTree as ET
from os import path
from pathlib import Path
from gpiozero import CPUTemperature
# todos / limitations:
# async image capture, processing and file i/o
# proper logging
# statistics for meta data (not just end of interval)

shutter_delay = args.internal_shutter_delay


def imager_config_vars(config_file):
    tree = ET.parse(config_file)
    fps_config = int(float(tree.getroot().find('framerate').text))
    sn_config = int(float(tree.getroot().find('serial').text))
    with open(args.imager_config_file, mode='r') as file:
        imager_config_file_contents = file.read()
    
    return {
        'fps': fps_config,
        'sn': sn_config,
        'imager_config_file_contents': imager_config_file_contents 
    }


def get_file_name(ssched, sn):
    file_end_raw = ssched.current_file_time_end()
    return str(sn) + '_' + \
        str(file_end_raw).replace("-", "").replace(":", "").replace(" ", "")


def preallocate_image_timeseries(x, y, t):
    return np.empty(
        [t, x, y],
        dtype=[
            ('snapshot', np.uint16),
            ('median', np.uint16),
            ('min', np.uint16),
            ('max', np.uint16),
            ('std', np.uint16),
        ]
    )


def preallocate_meta_timeseries(t):
    return np.empty(
        [t],
        dtype=[
            ('time', float),
            ('tbox', float),
            ('tchip', float),
            ('tpi', float),
            ('flag_state', np.uint16),
            ('counter', np.uint32),
            ('counterHW', np.uint32),
            ('fps', float),
            ('n_images', np.uint16),
        ]
    )


def app_setup():
    shutter = pixpy.Shutter()
    config_vars = imager_config_vars(args.imager_config_file)
    pixpy.usb_init_retry(args.imager_config_file)
    sn = pixpy.get_serial()
    if sn == 0:
        raise ValueError("Invalid serial number")
    if config_vars['sn'] != sn:
        raise ValueError(
            f'Found camera {sn} but expceted {args.imager_config_file}')
    pixpy.set_shutter_mode(0)
    shutter.trigger()
    sleep(shutter_delay * 2)
    return config_vars, shutter


def image_capture(config_vars, shutter):
    schedule_config = pixpy.config.read_schedule_config(
        args.schedule_config_file)
    Path(schedule_config['output_directory']).mkdir(parents=True,
                                                    exist_ok=True)
    ssched = pixpy.SnapshotSchedule(
        file_interval=timedelta(seconds=schedule_config['file_interval']),
        sample_interval=timedelta(seconds=schedule_config['sample_interval']),
        sample_repetition=timedelta(
            seconds=schedule_config['sample_repetition']),
    )
    width, height = pixpy.get_thermal_image_size()
    sample_timesteps_remaining = ssched.sample_timesteps_remaining()
    print(dt.utcnow())
    print(sample_timesteps_remaining)
    print(f'shutter_delay {shutter_delay}')
    sample_interval_s = ssched.sample_interval.total_seconds()
    print(f'sample_interval_s {sample_interval_s}')
    file_name = get_file_name(ssched, config_vars['sn'])
    image_timeseries = preallocate_image_timeseries(
        height, width, sample_timesteps_remaining)
    meta_timeseries = preallocate_meta_timeseries(sample_timesteps_remaining)
    n_images = int((sample_interval_s * config_vars['fps']) + 0.5)
    print(f'n_images {n_images}')
    print(f"fps {config_vars['fps']}")
    time_until_next_interval = ssched.current_sample_start() - \
        dt.utcnow() - timedelta(seconds=shutter_delay)
    print(f'time_until_next_interval {time_until_next_interval}')
    while (time_until_next_interval.total_seconds() - shutter_delay) < 0:
        time_until_next_interval = ssched.current_sample_start() - \
            dt.utcnow() - timedelta(seconds=shutter_delay)
    print(f"sleeping for {time_until_next_interval.total_seconds()}")
    sleep(time_until_next_interval.total_seconds())
    for j in range(0, sample_timesteps_remaining):
        dt_epoch = ssched.current_sample_start().replace(
            day=1, minute=0, hour=0, second=0, microsecond=0)
        dt_epoch_s = dt_epoch.timestamp()
        print(
            f'started n_interval_timestep {j + 1} / '
            f'{sample_timesteps_remaining} at {dt.utcnow()}'
        )
        shutter.trigger()
        print(f'shutter triggered {shutter._triggers} times')
        sleep(shutter_delay)
        print(f'waited for shutter until {dt.utcnow()}')
        interval_start_time = dt.utcnow()
        images_raw = np.empty((n_images, height, width), dtype=np.uint16)
        for i in range(0, n_images):
            image, meta = pixpy.get_thermal_image_metadata(width, height)
            images_raw[i, :, :] = image
            # print(f'got image {i} / {n_images} at {dt.utcnow()}')
        interval_end_time = dt.utcnow()
        print(f'interval has timestamp {interval_end_time}')
        dtime = interval_end_time - interval_start_time
        fps = n_images / dtime.total_seconds()
        image_timeseries['snapshot'][j, :, :] = image
        image_timeseries['median'][j, :, :] = np.median(images_raw, axis=0)
        image_timeseries['min'][j, :, :] = np.min(images_raw, axis=0)
        image_timeseries['max'][j, :, :] = np.max(images_raw, axis=0)
        image_timeseries['std'][j, :, :] = \
            (np.std((images_raw - 1000) / 10, axis=0) * 10) + 1000
        meta_timeseries['time'][j] = \
            (interval_end_time.timestamp() - dt_epoch_s) * 1000
        meta_timeseries['tbox'][j] = meta.tempBox
        meta_timeseries['tchip'][j] = meta.tempChip
        meta_timeseries['flag_state'][j] = meta.flagState
        meta_timeseries['counter'][j] = meta.counter
        meta_timeseries['counterHW'][j] = meta.counterHW
        meta_timeseries['fps'][j] = fps
        meta_timeseries['n_images'][j] = n_images
        meta_timeseries['tpi'][j] = CPUTemperature().temperature
        if j != (sample_timesteps_remaining - 1):
            next_interval_time = interval_start_time + ssched.sample_repetition
            current_time = dt.utcnow()
            wait_time_until_next_interval_s = (
                next_interval_time - current_time
            ).total_seconds() - shutter_delay
            print(f'Next interval in: {wait_time_until_next_interval_s} s')
            if wait_time_until_next_interval_s < 0:
                # todo: send to log file
                print("Next interval missed. Slow the sampling rate/fps.")
                wait_time_until_next_interval_s = 0
            sleep(wait_time_until_next_interval_s)
        else:
            next_sample_start_check = ssched.current_sample_start()
            x = np.arange(0, 160)
            y = np.flip(np.arange(0, 120))
            ds = xr.Dataset(
                data_vars=dict(
                    t_b_median=(
                        ["time", "y", "x"],
                        image_timeseries['median'],
                        {"units": "celsius",
                         "long_name": "brightness_temperature_median"}),
                    t_b_min=(
                        ["time", "y", "x"],
                        image_timeseries['min'],
                        {"units": "celsius",
                         "long_name": "brightness_temperature_min"}),
                    t_b_max=(
                        ["time", "y", "x"],
                        image_timeseries['max'],
                        {"units": "celsius",
                         "long_name": "brightness_temperature_max"}),
                    t_b_std=(
                        ["time", "y", "x"],
                        image_timeseries['std'],
                        {"units": "celsius",
                         "long_name":
                             "brightness_temperature_standard_deviation"}),
                    t_b_snapshot=(
                        ["time", "y", "x"],
                        image_timeseries['snapshot'],
                        {"units": "celsius",
                         "long_name": "brightness_temperature_snapshot"}),
                    t_box=(
                        ["time"],
                        meta_timeseries['tbox'],
                        {"units": "celsius",
                         "long_name": "temperature_camera_body"}),
                    t_chip=(
                        ["time"],
                        meta_timeseries['tchip'],
                        {"units": "celsius",
                         "long_name": "temperature_focal_plane_array_chip"}),
                    flag_state=(
                        ["time"],
                        meta_timeseries['flag_state'],
                        {"long_name": "flag_status"}),
                    counter=(
                        ["time"],
                        meta_timeseries['counter'],
                        {"long_name": "image_counter_from_software"}),
                    counterHW=(
                        ["time"],
                        meta_timeseries['counterHW'],
                        {"long_name": "image_counter_from_hardware"}),
                    frames=(
                        ["time"],
                        meta_timeseries['fps'],
                        {"units": "s-1", "long_name": "frames_per_second"}),
                    n_images=(
                        ["time"],
                        meta_timeseries['n_images'],
                        {"long_name": "number_of_images_in_interval"}),
                    t_cpu=(
                        ["time"],
                        meta_timeseries['tpi'],
                        {"long_name": "temperature_raspberry_pi_cpu"}),
                ),
                coords=dict(
                    x=x,
                    y=y,
                    time=meta_timeseries['time'],
                ),
                # todo: add contents of config files to netcdf.
                attrs=dict(
                    description="pixpy",
                    serial=config_vars['sn'],
                    brightness_temperature_scaling="10",
                    brightness_temperature_offset="1000",
                    imager_config_file_contents=config_vars["imager_config_file_contents"],
                ),
            )
            ds.x.attrs['long_name'] = 'pixels_along_x_axis'
            ds.y.attrs['long_name'] = 'pixels_along_y_axis'
            ds.time.attrs['units'] = dt_epoch.strftime(
                'milliseconds since %Y-%m-%d')
            ds.time.attrs['long_name'] = 'time'
            ds.time.attrs['standard_name'] = 'time'

            ds.to_netcdf(path.join(schedule_config['output_directory'],
                                   f'{file_name}.nc'),
                         encoding={
                'time': {'zlib': True, "complevel": 5, '_FillValue': -999},
                't_b_median': {'zlib': True, "complevel": 5},
                't_b_min': {'zlib': True, "complevel": 5},
                't_b_max': {'zlib': True, "complevel": 5},
                't_b_std': {'zlib': True, "complevel": 5},
                't_b_snapshot': {'zlib': True, "complevel": 5},
                'n_images': {'zlib': True, "complevel": 5},
            },
                unlimited_dims=["time"])
            if (next_sample_start_check < dt.utcnow()):
                print("missed sample: i/o blocking")


def app():
    while True:
        try:
            config_vars, shutter = app_setup()
        except (RuntimeError, ValueError) as e:
            print(e)
            sleep(5)
        while True:
            try:
                image_capture(config_vars, shutter)
            except (RuntimeError, ValueError) as e:
                print(e)
                sleep(1)
                try:
                    pixpy.terminate()
                except (RuntimeError, ValueError) as e:
                    print(e)
                sleep(1)
                break

