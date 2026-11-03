#!/bin/sh
# Customer reply to a case: ./reply.sh <caseId> "<text>" [--image FILE] [--attach]
exec python3 "$(dirname "$0")/send_demo_email.py" reply "$@"
