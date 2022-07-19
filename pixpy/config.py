import xml.etree.cElementTree as ET
import xml.dom.minidom

DEFAULT_FILE_INTERVAL = "300"
DEFAULT_SAMPLE_INTERVAL = "5"
DEFAULT_SAMPLE_REPETITION = "60"
DEFAULT_IMAGER_CONFIG_FILE = 'config.xml'
DEFAULT_OUTPUT_DIRECTORY = 'OUT'


def write_schedule_config(file_name):

    m_encoding = 'UTF-8'
    root = ET.Element("schedule_config")
    ET.SubElement(
        root, "file_interval",
        description="The time interval for one image file.").text = \
        DEFAULT_FILE_INTERVAL
    ET.SubElement(
        root, "sample_interval",
        description="The time interval to capture one image aggregate.").text = \
        DEFAULT_SAMPLE_INTERVAL
    ET.SubElement(
        root, "sample_repetition",
        description="The time interval between image samples.").text = \
        DEFAULT_SAMPLE_REPETITION
    ET.SubElement(
        root, "output_directory",
        description="The directory where image files are saved.").text = \
        DEFAULT_OUTPUT_DIRECTORY
    dom = xml.dom.minidom.parseString(ET.tostring(root))
    xml_string = dom.toprettyxml()
    part1, part2 = xml_string.split('?>')
    with open(file_name, 'w') as xfile:
        xfile.write(part1 + 'encoding=\"{}\"?>\n'.format(m_encoding) + part2)
        xfile.close()


def read_schedule_config(config_file):
    tree = ET.parse(config_file)
    return {
        'file_interval': float(tree.getroot().find('file_interval').text),
        'sample_interval': float(tree.getroot().find('sample_interval').text),
        'sample_repetition': float(tree.getroot().find('sample_repetition').text),
        'output_directory': tree.getroot().find('output_directory').text,
        }
