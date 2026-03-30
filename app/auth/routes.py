"""
app/campus/routes.py
════════════════════
Resources + Web Push Subscription endpoints.
"""

import json
from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin

campus_bp = Blueprint('campus', __name__)


# ══════════════════════════════════════════════════════════════
# RESOURCES
# ══════════════════════════════════════════════════════════════

@campus_bp.route('/resources')
def resources_page():
    return render_template('modules/resources.html')


@campus_bp.route('/api/resources', methods=['GET'])
def get_resources():
    dept    = request.args.get('dept', '')
    subject = request.args.get('subject', '')
    sb = get_supabase_admin()
    try:
        q = sb.table('resources').select('*')
        if dept:
            q = q.eq('dept', dept)
        if subject:
            q = q.ilike('subject', f'%{subject}%')
        resp = q.order('created_at', desc=True).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@campus_bp.route('/api/resources', methods=['POST'])
def upload_resource():
    data = request.get_json() or {}
    sb = get_supabase_admin()
    try:
        payload = {
            'dept':        data.get('dept', 'Management'),
            'subject':     data.get('subject', ''),
            'file_url':    data.get('file_url', ''),
            'title':       data.get('title', ''),
            'uploaded_by': data.get('uploaded_by', ''),
        }
        resp = sb.table('resources').insert(payload).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@campus_bp.route('/api/resources/<resource_id>', methods=['DELETE'])
def delete_resource(resource_id):
    sb = get_supabase_admin()
    try:
        sb.table('resources').delete().eq('id', resource_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════
# WEB PUSH SUBSCRIPTIONS
# ══════════════════════════════════════════════════════════════

@campus_bp.route('/api/push-subscribe', methods=['POST'])
def push_subscribe():
    """
    Save a browser's Web Push subscription to Supabase.
    Called automatically by push-client.js after user grants notification permission.
    """
    data = request.get_json() or {}
    user_id      = data.get('user_id', '')
    subscription = data.get('subscription', {})

    if not user_id or not subscription:
        return jsonify({'success': False, 'error': 'user_id and subscription required'}), 400

    endpoint = subscription.get('endpoint', '')
    if not endpoint:
        return jsonify({'success': False, 'error': 'invalid subscription'}), 400

    sb = get_supabase_admin()
    try:
        # Upsert by (user_id, endpoint) so re-subscribing doesn't create duplicates
        sb.table('push_subscriptions').upsert({
            'user_id':           user_id,
            'endpoint':          endpoint,
            'subscription_json': json.dumps(subscription),
        }, on_conflict='user_id,endpoint').execute()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@campus_bp.route('/api/push-unsubscribe', methods=['POST'])
def push_unsubscribe():
    """Remove a push subscription (called when user revokes permission)."""
    data = request.get_json() or {}
    user_id  = data.get('user_id', '')
    endpoint = data.get('endpoint', '')

    if not user_id:
        return jsonify({'success': False, 'error': 'user_id required'}), 400

    sb = get_supabase_admin()
    try:
        q = sb.table('push_subscriptions').delete().eq('user_id', user_id)
        if endpoint:
            q = q.eq('endpoint', endpoint)
        q.execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@campus_bp.route('/api/push-vapid-key', methods=['GET'])
def get_vapid_public_key():
    """Return the VAPID public key so push-client.js can subscribe."""
    import os
    key = os.environ.get('VAPID_PUBLIC_KEY', '')
    if not key:
        return jsonify({'success': False, 'error': 'Push not configured'}), 503
    return jsonify({'success': True, 'public_key': key})