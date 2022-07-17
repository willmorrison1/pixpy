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
    )

args = parser.parse_args()

