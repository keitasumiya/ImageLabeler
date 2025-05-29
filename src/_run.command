#!/bin/bash

set -CEuo pipefail
SCRIPT_DIR=$(cd $(dirname $0) && pwd)
#echo ${SCRIPT_DIR}
cd ${SCRIPT_DIR}

python3 imageLabeler.py



# exit