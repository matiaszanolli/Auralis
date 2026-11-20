#!/usr/bin/env bash

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${AURALIS_PYTHON:-python}" "$root/launch-auralis-web.py" --dev "$@"
