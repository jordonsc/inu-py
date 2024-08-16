#!/usr/bin/env bash

# Update Inu on PyPi -
rm -rf dist build inu_net.egg-info

python3 setup.py sdist
python3 setup.py bdist_wheel --universal
twine upload dist/*
