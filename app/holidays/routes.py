"""
app/holidays/routes.py
======================
RUB Holiday Blueprint — URL prefix: /holidays

All data & enrichment logic live in core/holidays.py.
This file only defines Flask routes.

Smart countdown rules (enforced in core/holidays.py):
  total_days > 12  →  show countdown 4 days before start
  total_days >  7  →  show countdown 3 days before start
  total_days >  3  →  show countdown 2 days before start
  total_days <= 3  →  show countdown 1 day  before start
"""

from flask import Blueprint, jsonify, render_template
from core.holidays import get_all_enriched

holidays_bp = Blueprint('holidays', __name__)


# ── Pages ─────────────────────────────────────────────────────

@holidays_bp.route('/')
def holidays_page():
    return render_template('modules/holidays.html')


# ── API ───────────────────────────────────────────────────────

@holidays_bp.route('/api/holidays')
def api_holidays():
    """All holidays enriched with status, countdown, days_until."""
    enriched = get_all_enriched()
    return jsonify({'success': True, 'data': enriched, 'total': len(enriched)})


@holidays_bp.route('/api/holidays/countdown')
def api_countdown():
    """
    Only holidays that are currently ongoing OR within their
    countdown window. Used by the dashboard banner.
    """
    enriched  = get_all_enriched()
    in_window = [
        h for h in enriched
        if h['status'] == 'ongoing'
        or (h['status'] == 'upcoming' and h.get('show_countdown'))
    ]
    in_window.sort(key=lambda h: h['start'])
    return jsonify({'success': True, 'data': in_window})