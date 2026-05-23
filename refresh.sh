#!/bin/bash
# Refresh dashboard data from Odoo and push to GitHub
cd "$(dirname "$0")"
python3 generate_data.py
git add data.json
git commit -m "Auto-refresh: $(date '+%Y-%m-%d %H:%M')"
git push
echo "Dashboard refreshed!"
