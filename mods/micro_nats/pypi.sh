#!/usr/bin/env bash

# Update MicroNats on PyPi -
rm -rf dist build micro_nats.egg-info

python3 setup.py sdist
python3 setup.py bdist_wheel --universal
twine upload dist/*
