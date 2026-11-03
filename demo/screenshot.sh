#!/bin/sh
# One-command demo email: screenshot. Extra options (--image FILE, --attach, --dry-run) are passed through.
exec python3 "$(dirname "$0")/send_demo_email.py" screenshot "$@"
