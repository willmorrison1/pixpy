from argparse import ArgumentParser

parser = ArgumentParser()

parser.add_argument(
    '--imager_config_file',
    type=str,
    help='The libirimager configuration file (.xml)',
    required=True,
    )
parser.add_argument(
    '--schedule_config_file',
    type=str,
    help='The image capture schedule file (.xml)',
    required=True,
    )
parser.add_argument(
    '--internal_shutter_delay',
    type=int,
    help='The specified time for the internal shutter to cycle (s)',
    required=False,
    default=0.3
    )
args = parser.parse_args()
