#!/bin/bash

# This script should be run from the repo's deployment directory
# cd deployment
# ./run-unit-tests.sh

# Run unit tests
echo "Running unit tests"
echo "cd ../source"
cd ../source
echo "Running Unit Tests ..."
echo "cd captionlambda"
cd captionlambda
echo "python3.6 unit_tests.py"
python3.6 unit_tests.py
echo "Completed unit tests"
