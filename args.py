from argparse import ArgumentParser
import xml.etree.cElementTree as ET
import xml.dom.minidom

DEFAULT_FILE_INTERVAL = "300"
DEFAULT_SAMPLE_INTERVAL = "60"
DEFAULT_SAMPLE_REPETITION = "5"
DEFAULT_IMAGER_CONFIG_FILE = 'config.xml'
DEFAULT_OUTPUT_DIRECTORY = 'OUT'

def write_schedule_config_file():

    m_encoding = 'UTF-8'
    
    root = ET.Element("schedule_config")
    ET.SubElement(
        root, "file_interval", 
        description="The time interval for one image file.").text = DEFAULT_FILE_INTERVAL
    ET.SubElement(
        root, "sample_interval",
        description="The time interval to capture one image aggregate.").text = DEFAULT_SAMPLE_INTERVAL
    ET.SubElement(
        root, "sample_repetition",
        description="The time interval between image samples.").text = DEFAULT_SAMPLE_REPETITION
    ET.SubElement(
        root, "output_directory",
        description="The directory where image files are saved.").text = DEFAULT_OUTPUT_DIRECTORY
    dom = xml.dom.minidom.parseString(ET.tostring(root))
    xml_string = dom.toprettyxml()
    part1, part2 = xml_string.split('?>')
    
    with open("FILE.xml", 'w') as xfile:
        xfile.write(part1 + 'encoding=\"{}\"?>\n'.format(m_encoding) + part2)
        xfile.close()

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

