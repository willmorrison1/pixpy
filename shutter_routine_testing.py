# -*- coding: utf-8 -*-
"""
Created on Sun Jul 17 12:55:27 2022

@author: willm
"""
from pixpy import SnapshotSchedule
import config
from datetime import timedelta, datetime as dt
from time import sleep


schedule_config_file = "schedule_config.xml"
schedule_config = config.read_schedule_config(schedule_config_file)

MOTOR_MOVE_TIME_S = 1
GRACE_TIME_S = 1

def shutter_open():
    print(f"Opening shutter{dt.utcnow()}")

def shutter_close():
    print(f"Closing shutter{dt.utcnow()}")

def activate_shutter(ssched):
    time_now = dt.utcnow()
    next_sample = ssched.current_sample_start()
    time_until_next_sample = (next_sample - time_now).total_seconds() - \
        MOTOR_MOVE_TIME_S - GRACE_TIME_S
    if time_until_next_sample < 0:
        return None
    print(f"Sleeping for {time_until_next_sample} s")
    sleep(time_until_next_sample)
    shutter_open()
    time_until_sample_finished = ssched.sample_interval.total_seconds() +\
        MOTOR_MOVE_TIME_S + (GRACE_TIME_S * 2)
    sleep(time_until_sample_finished)
    shutter_close()

def external_shutter_app():
    ssched = SnapshotSchedule(
        file_interval=timedelta(seconds=schedule_config['file_interval']),
        sample_interval=timedelta(seconds=schedule_config['sample_interval']),
        sample_repetition=timedelta(seconds=schedule_config['sample_repetition']),
        )
    sample_timesteps_remaining = ssched.sample_timesteps_remaining()
    if sample_timesteps_remaining < 0:
        sleep(0.5)
        return None
    for i in range(0, sample_timesteps_remaining):
        activate_shutter(ssched)
        
if __name__ == "__main__":
    while True:
        external_shutter_app()
