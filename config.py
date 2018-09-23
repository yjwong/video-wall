import os
import sys

import yaml

def get_config():
    # Load the configuration and credentials from YAML.
    config_path = os.path.join(sys.path[0], "config.yaml")
    return yaml.safe_load(open(config_path))
