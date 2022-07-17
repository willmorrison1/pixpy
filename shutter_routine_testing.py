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

ssched = SnapshotSchedule(
    file_interval=timedelta(seconds=schedule_config['file_interval']),
    sample_interval=timedelta(seconds=schedule_config['sample_interval']),
    sample_repetition=timedelta(seconds=schedule_config['sample_repetition']),
    )

def shutter_open():
    print("Opening shutter")

def shutter_close():
    print("Closing shutter")

time_now = dt.utcnow()
next_sample = ssched.current_sample_start()
# wait for next sample start 
sleep((next_sample - time_now).total_seconds() - MOTOR_MOVE_TIME_S)
shutter_open()
sleep(ssched.sample_interval.total_seconds())
shutter_close()

