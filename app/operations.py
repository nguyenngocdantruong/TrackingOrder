"""Structured operational records. Only identifiers and diagnostic metadata are stored."""
from datetime import datetime, timezone

from flask import current_app, has_app_context
from google.cloud import firestore

from app.firebase import get_db


def record(kind, action, outcome, **references):
    if not has_app_context():
        return
    entry = {
        'kind': kind, 'action': action, 'outcome': outcome,
        'createdAt': datetime.now(timezone.utc),
    }
    for key in ('actorId', 'userId', 'trackingId', 'carrierId', 'channel',
                'stage', 'statusCode', 'deliveryId', 'processed', 'failed'):
        if references.get(key) is not None:
            entry[key] = references[key]
    try:
        db = get_db()
        events = db.collection('operation_events')
        if kind == 'scheduler':
            batch = db.batch()
            batch.set(events.document(), entry)
            batch.set(db.collection('operation_state').document('scheduler'), entry)
            batch.commit()
        else:
            events.add(entry)
    except Exception:
        current_app.logger.warning('Could not record operation %s/%s', kind, action)


def record_payment(order_code, amount, paid=False):
    """Store PayOS status and claim a paid event once, even on webhook retries."""
    if not order_code or not str(order_code).isdigit():
        return True
    db = get_db()
    ref = db.collection('donation_history').document(str(order_code))

    @firestore.transactional
    def save(transaction):
        previous = ref.get(transaction=transaction)
        if previous.exists and previous.to_dict().get('status') == 'paid':
            return False
        data = {
            'orderCode': str(order_code),
            'amount': amount,
            'updatedAt': firestore.SERVER_TIMESTAMP,
            'status': 'paid' if paid else 'pending',
        }
        if not previous.exists:
            data['createdAt'] = firestore.SERVER_TIMESTAMP
        transaction.set(ref, data, merge=True)
        return True

    return save(db.transaction())
