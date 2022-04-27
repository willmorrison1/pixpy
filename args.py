from argparse import ArgumentParser

parser = ArgumentParser()

parser.add_argument(
    '--config_file', 
    type=str, 
    help='The config.xml file', 
    required=True,
    )
parser.add_argument(
    '--file_interval',
    type=int, 
    help='The time period covered by each file (seconds)', 
    default=300,
    )
parser.add_argument(
    '--sample_interval',
    type=int, 
    help='The time period covered by a sample (seconds)', 
    default=5,
    )
parser.add_argument(
    '--sample_resolution',
    type=int, 
    help='The length of time between samples (seconds)',
    default=60,
    )
parser.add_argument(
    '--output_directory', 
    type=str, 
    help='The name of the output directory', 
    default='OUT',
    )

args = parser.parse_args()
