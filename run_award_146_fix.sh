#!/bin/bash
set -euo pipefail
cd /var/www/mmo
source venv/bin/activate
python fix_award_146_medals.py
