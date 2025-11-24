"""
Notification routes for in-app notifications system
Provides API endpoints for notifications management
"""
from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required, current_user
from datetime import datetime
from database import SessionLocal
from models import Notification
from sqlalchemy import desc

notification_bp = Blueprint('notifications', __name__)


@notification_bp.route('/api/notifications/unread-count')
@login_required
def get_unread_count():
    """Get count of unread notifications for current user"""
    db = SessionLocal()
    try:
        count = db.query(Notification).filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False
        ).count()

        return jsonify({'count': count})
    finally:
        db.close()


@notification_bp.route('/api/notifications')
@login_required
def get_notifications():
    """Get all notifications for current user with pagination"""
    db = SessionLocal()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'

        # Build query
        query = db.query(Notification).filter(
            Notification.user_id == current_user.id
        )

        if unread_only:
            query = query.filter(Notification.is_read == False)

        # Order by created_at desc (newest first)
        query = query.order_by(desc(Notification.created_at))

        # Paginate
        total = query.count()
        notifications = query.limit(per_page).offset((page - 1) * per_page).all()

        return jsonify({
            'notifications': [n.to_dict() for n in notifications],
            'total': total,
            'page': page,
            'per_page': per_page,
            'has_next': page * per_page < total,
            'has_prev': page > 1
        })
    finally:
        db.close()


@notification_bp.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a specific notification as read"""
    db = SessionLocal()
    try:
        notification = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id  # SECURITY: verify ownership
        ).first()

        if not notification:
            return jsonify({'error': 'Notification not found'}), 404

        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            db.commit()

        return jsonify({'success': True})
    finally:
        db.close()


@notification_bp.route('/api/notifications/read-all', methods=['POST'])
@login_required
def mark_all_read():
    """Mark all notifications as read for current user"""
    db = SessionLocal()
    try:
        db.query(Notification).filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False
        ).update({
            'is_read': True,
            'read_at': datetime.utcnow()
        })
        db.commit()

        return jsonify({'success': True})
    finally:
        db.close()


@notification_bp.route('/notifications')
@login_required
def notifications_page():
    """Notifications page with full list"""
    db = SessionLocal()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20

        # Get notifications
        query = db.query(Notification).filter(
            Notification.user_id == current_user.id
        ).order_by(desc(Notification.created_at))

        total = query.count()
        notifications = query.limit(per_page).offset((page - 1) * per_page).all()

        # Get unread count
        unread_count = db.query(Notification).filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False
        ).count()

        return render_template(
            'notifications.html',
            notifications=notifications,
            unread_count=unread_count,
            total=total,
            page=page,
            per_page=per_page,
            has_next=page * per_page < total,
            has_prev=page > 1
        )
    finally:
        db.close()


def create_notification(user_id, message, notification_type='info', link_url=None, link_text=None):
    """
    Helper function to create a notification

    Args:
        user_id: ID of the user to notify
        message: Notification message
        notification_type: Type of notification ('info', 'success', 'warning', 'error')
        link_url: Optional URL to link to
        link_text: Optional link text (e.g., "Voir le document")

    Returns:
        Notification object or None if failed
    """
    db = SessionLocal()
    try:
        notification = Notification(
            user_id=user_id,
            message=message,
            notification_type=notification_type,
            link_url=link_url,
            link_text=link_text
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification
    except Exception as e:
        print(f"[NOTIFICATION] Error creating notification: {e}")
        db.rollback()
        return None
    finally:
        db.close()
