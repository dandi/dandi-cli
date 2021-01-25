import sys
from dandi.metadata import publish_model_schemata

if __name__ == "__main__":
    publish_model_schemata(sys.argv[1])
