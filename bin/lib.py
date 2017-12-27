import datetime
import logging
import os
import string
import tempfile

import numpy
import pandas
import re
import yaml

# Global variables
from keras.preprocessing.sequence import pad_sequences

CONFS = None
BATCH_NAME = None
TEMP_DIR = None
CHAR_INDICES = None
INDICES_CHAR = None


def load_confs(confs_path='../conf/conf.yaml'):
    """
    Load configurations from file.

     - If configuration file is available, load it
     - If configuraiton file is not available attempt to load configuration template

    Configurations are never explicitly validated.
    :param confs_path: Path to a configuration file, appropriately formatted for this application
    :type confs_path: str
    :return: Python native object, containing configuration names and values
    :rtype: dict
    """
    global CONFS

    if CONFS is None:

        try:
            logging.info('Attempting to load conf from path: {}'.format(confs_path))

            # Attempt to load conf from confPath
            CONFS = yaml.load(open(confs_path))

        except IOError:
            logging.warn('Unable to open user conf file. Attempting to run with default values from conf template')

            # Attempt to load conf from template path
            template_path = confs_path + '.template'
            CONFS = yaml.load(open(template_path))

    return CONFS


def get_conf(conf_name):
    """
    Get a configuration parameter by its name
    :param conf_name: Name of a configuration parameter
    :type conf_name: str
    :return: Value for that conf (no specific type information available)
    """
    return load_confs()[conf_name]


def get_batch_name():
    """
    Get the name of the current run. This is a unique identifier for each run of this application
    :return: The name of the current run. This is a unique identifier for each run of this application
    :rtype: str
    """
    global BATCH_NAME

    if BATCH_NAME is None:
        logging.info('Batch name not yet set. Setting batch name.')
        BATCH_NAME = str(datetime.datetime.utcnow()).replace(' ', '_').replace('/', '_').replace(':', '_')
        logging.info('Batch name: {}'.format(BATCH_NAME))
    return BATCH_NAME


def get_temp_dir():
    global TEMP_DIR
    if TEMP_DIR is None:
        TEMP_DIR = tempfile.mkdtemp(prefix='reddit_')
        logging.info('Created temporary directory: {}'.format(TEMP_DIR))
        print('Created temporary directory: {}'.format(TEMP_DIR))
    return TEMP_DIR


def archive_dataset_schemas(step_name, local_dict, global_dict):
    """
    Archive the schema for all available Pandas DataFrames

     - Determine which objects in namespace are Pandas DataFrames
     - Pull schema for all available Pandas DataFrames
     - Write schemas to file

    :param step_name: The name of the current operation (e.g. `extract`, `transform`, `model` or `load`
    :param local_dict: A dictionary containing mappings from variable name to objects. This is usually generated by
    calling `locals`
    :type local_dict: dict
    :param global_dict: A dictionary containing mappings from variable name to objects. This is usually generated by
    calling `globals`
    :type global_dict: dict
    :return: None
    :rtype: None
    """
    logging.info('Archiving data set schema(s) for step name: {}'.format(step_name))

    # Reference variables
    data_schema_dir = get_conf('data_schema_dir')
    schema_output_path = os.path.join(data_schema_dir, step_name + '.csv')
    schema_agg = list()

    env_variables = dict()
    env_variables.update(local_dict)
    env_variables.update(global_dict)

    # Filter down to Pandas DataFrames
    data_sets = filter(lambda (k, v): type(v) == pandas.DataFrame, env_variables.iteritems())
    data_sets = dict(data_sets)

    header = pandas.DataFrame(columns=['variable', 'type', 'data_set'])
    schema_agg.append(header)

    for (data_set_name, data_set) in data_sets.iteritems():
        # Extract variable names
        logging.info('Working data_set: {}'.format(data_set_name))

        local_schema_df = pandas.DataFrame(data_set.dtypes, columns=['type'])
        local_schema_df['data_set'] = data_set_name

        schema_agg.append(local_schema_df)

    # Aggregate schema list into one data frame
    agg_schema_df = pandas.concat(schema_agg)

    # Write to file
    agg_schema_df.to_csv(schema_output_path, index_label='variable')

def legal_characters():
    chars = set(string.printable + '<>')
    chars.remove('\n')
    chars.remove('\r')
    return chars

def get_char_indices():
    global CHAR_INDICES
    if CHAR_INDICES is None:
        chars = sorted(list(set(legal_characters())))
        CHAR_INDICES = dict((c, i) for i, c in enumerate(chars))
    return CHAR_INDICES

def get_indices_char():
    global INDICES_CHAR
    if INDICES_CHAR is None:
        chars = sorted(list(set(legal_characters())))
        INDICES_CHAR = dict((i, c) for i, c in enumerate(chars))
    return INDICES_CHAR

def gen_x_y(uncleaned_text, y_list=None):
    logging.info('Generating X and Y')

    # Reference vars
    chars = sorted(list(set(legal_characters())))
    char_indices = get_char_indices()
    indices_char = get_indices_char()
    cleaned_text_chars = list()
    cleaned_text_indices = list()

    for text in uncleaned_text:
        logging.debug('Raw text: {}'.format(text))

        text = map(lambda x: x.lower(), text)
        text = map(lambda x: x if x in legal_characters() else ' ', text)
        text = ''.join(text)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        # Add start and end characters
        text = re.sub('<', ' ', text)
        text = re.sub('>', ' ', text)
        text = '<' + text + '>'

        logging.debug('Cleaned text: {}'.format(text))
        cleaned_text_chars.append(text)

        text_indices = map(lambda x: char_indices[x], text)
        logging.debug('Cleaned text indices: {}'.format(text_indices))
        cleaned_text_indices.append(text_indices)

    # Convert all sequences into X and Y matrices
    x = pad_sequences(cleaned_text_indices, maxlen=get_conf('x_maxlen'), value= max(indices_char.keys())+1)
    y = numpy.array(y_list, dtype=bool)

    return x, y