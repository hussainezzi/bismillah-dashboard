#!/bin/bash
# Refresh Bismillah Traders dashboard data from Odoo and push to GitHub
cd /data/.openclaw/workspace-accounting/bismillah-dashboard
python3 generate_data.py && \
git add data.json && \
git commit -m "Auto-update data $(date +'%Y-%m-%d %H:%M')" && \
git push origin main
