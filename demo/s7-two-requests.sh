#!/bin/sh
# One-command demo email: s7-two-requests. Extra options (--image FILE, --attach, --dry-run) are passed through.
exec python3 "$(dirname "$0")/send_demo_email.py" s7-two-requests "$@"
