#!/bin/sh
# One-command demo email: s1-no-card. Extra options (--image FILE, --attach, --dry-run) are passed through.
exec python3 "$(dirname "$0")/send_demo_email.py" s1-no-card "$@"
