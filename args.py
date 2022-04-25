from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('--config_file', type=str, help='The config.xml file', 
                    default='config.xml')
parser.add_argument('--file_interval_length', type=int, 
                    help='The time interval for each file (seconds)', default=300)
parser.add_argument('--sample_length', type=int, 
                    help='The lenght of time for a sample (seconds)', default=5)
parser.add_argument('--repeat_any', type=int, 
                    help='The length of time between samples (seconds)', default=60)
parser.add_argument('--output_directory', type=str, 
                    help='The name of the output directory', default='OUT')
args = parser.parse_args()