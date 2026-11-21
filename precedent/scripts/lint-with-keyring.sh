#!/usr/bin/env bash
set -euo pipefail
eval "$(printf '\n' | gnome-keyring-daemon --unlock --components=secrets)"
forge lint
