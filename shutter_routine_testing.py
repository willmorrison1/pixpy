# -*- coding: utf-8 -*-
"""
Created on Sun Jul 17 12:55:27 2022

@author: willm
"""
from pixpy import SnapshotSchedule
import config
from datetime import timedelta, datetime as dt
from time import sleep
from dataclasses import dataclass
from argparse import ArgumentParser

parser = ArgumentParser()

parser.add_argument(
    '--servo_move_time', 
    type=float, 
    help='The time it takes for the servo to move (s).', 
    required=False,
    default=1,
    )
parser.add_argument(
    '--grace_time',
    type=float, 
    help='A time window to account for any time offsets between applications (s).',
    required=False,
    default=1,
    )
parser.add_argument(
    '--schedule_config_file',
    type=str, 
    help='The image capture schedule file (.xml)', 
    default="schedule_config.xml",
    )

args = parser.parse_args()

@dataclass(frozen=True)  # todo: docstr
class ShutterSnapshotSchedule(SnapshotSchedule):
    servo_move_time: timedelta = timedelta(seconds=1)
    grace_time: timedelta = timedelta(seconds=1)

    def total_grace_time(self):
        return self.servo_move_time + self.grace_time
    def __post_init__(self):
        if (self.total_grace_time() * 2) >= self.sample_repetition:
            raise ValueError(
                'Servo takes longer to move than the sample repetition. \
                    Slow the sample repetition or reduce the servo grace time')

def shutter_open():
    print(f"Opening shutter{dt.utcnow()}")

def shutter_close():
    print(f"Closing shutter{dt.utcnow()}")

def activate_shutter(ssched):
    time_now = dt.utcnow()
    next_sample = ssched.current_sample_start()
    time_until_next_sample = (next_sample - time_now).total_seconds() - \
        ssched.total_grace_time().total_seconds()
    if time_until_next_sample < 0:
        sleep(0.5)
        return None
    sleep(time_until_next_sample)
    print(f"Doing interval {ssched.current_sample_start()} - {ssched.current_sample_end()}")
    shutter_open()
    time_until_sample_finished = ssched.sample_interval.total_seconds() +\
        ssched.total_grace_time().total_seconds() + ssched.grace_time.total_seconds()
    sleep(time_until_sample_finished)
    shutter_close()

def external_shutter_app():
    schedule_config = config.read_schedule_config(args.schedule_config_file)
    ssched = ShutterSnapshotSchedule(
        file_interval=timedelta(seconds=schedule_config['file_interval']),
        sample_interval=timedelta(seconds=schedule_config['sample_interval']),
        sample_repetition=timedelta(seconds=schedule_config['sample_repetition']),
        servo_move_time=timedelta(seconds=args.servo_move_time),
        grace_time=timedelta(seconds=args.grace_time),
        )
    sample_timesteps_remaining = ssched.sample_timesteps_remaining()
    if sample_timesteps_remaining < 0:
        print("No timesteps")
        return None
    for i in range(0, sample_timesteps_remaining):
        activate_shutter(ssched)
        
if __name__ == "__main__":
    while True:
        try:
            external_shutter_app()
        except ValueError as e:
            print(e)
            sleep(5)
            continue
