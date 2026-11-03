#!/bin/sh
# Fraud team reply: ./fraud-reply.sh <caseId> keep|remove|"<text>"
exec python3 "$(dirname "$0")/send_demo_email.py" fraud-reply "$@"
