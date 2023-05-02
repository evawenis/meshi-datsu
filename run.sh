#!/bin/bash

mkdir "$HOME"/firefox-tmp
export TMPDIR="$HOME"/firefox-tmp
chmod 777 "$TMPDIR"
python3 reserver.py