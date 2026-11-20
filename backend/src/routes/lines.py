from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.constants.enums import LineOrderStatus
from src.models import LineHandover, LineOrder, LineState
from src.schemas.line import CancelInput, HandoverInput, LineOrderInput
from src.middlewares.auth import current_user, can_write, admin_only
from src.services import lines
from src.services.audit import record
from src.utils.serialization import line_handover_dict, line_order_dict

router = APIRouter(prefix='/lines')


def _order(db, order_id):
    order = db.get(LineOrder, order_id)
    if not order:
        raise HTTPException(404, '换线单不存在')
    return order


@router.get('')
def listing(db=Depends(get_db), u=Depends(current_user)):
    rows = list(db.scalars(select(LineOrder).order_by(LineOrder.id.desc()).limit(200)))
    receipts = {}
    if rows:
        for h in db.scalars(select(LineHandover).where(LineHandover.order_id.in_([o.id for o in rows])).order_by(LineHandover.id)):
            receipts.setdefault(h.order_id, []).append(line_handover_dict(h))
    return [{**line_order_dict(o), 'handovers': receipts.get(o.id, [])} for o in rows]


@router.get('/board')
def board(db=Depends(get_db), u=Depends(current_user)):
    return [{'team': b['team'], 'current_line': b['current_line'], 'updated_at': b['updated_at'],
             'pending_order': line_order_dict(b['pending_order']) if b['pending_order'] else None,
             'effective_order': line_order_dict(b['effective_order']) if b['effective_order'] else None,
             'latest_order': line_order_dict(b['latest_order']) if b['latest_order'] else None}
            for b in lines.board(db)]


@router.post('', status_code=201)
def create(data: LineOrderInput, db=Depends(get_db), u=Depends(can_write)):
    order = lines.create(db, data, u)
    record(db, u.email, 'line.order.create',
           {'id': order.id, 'team': order.team, 'from': order.from_line, 'to': order.to_line, 'job': order.job_id})
    db.commit()
    return line_order_dict(order)


@router.get('/{id}')
def detail(id: int, db=Depends(get_db), u=Depends(current_user)):
    order = _order(db, id)
    handovers = db.scalars(select(LineHandover).where(LineHandover.order_id == id).order_by(LineHandover.id))
    chain = lines.history(db, id)
    state = db.scalar(select(LineState).where(LineState.team == order.team))
    return {**line_order_dict(order), 'handovers': [line_handover_dict(h) for h in handovers],
            'chain': [line_order_dict(o) for o in chain],
            'current_line': state.current_line if state else lines.DEFAULT_LINE,
            'switched': order.status in (LineOrderStatus.effective.value, LineOrderStatus.reversed.value)}


@router.post('/{id}/handover')
def handover(id: int, data: HandoverInput, db=Depends(get_db), u=Depends(can_write)):
    order, outcome = lines.handover(db, id, data, u)
    if outcome.get('idempotent'):
        db.commit()  # 已存在的回执不重复记审计或改状态
        return {**line_order_dict(order), 'idempotent': True, 'switched': order.status == LineOrderStatus.effective.value}
    record(db, u.email, 'line.handover.' + data.side,
           {'id': id, 'receipt': data.receipt_id, 'switched': outcome.get('switched', False)})
    if outcome.get('switched'):
        record(db, u.email, 'line.order.effective', {'id': id, 'team': order.team,
                                                     'from': order.from_line, 'to': order.to_line})
    db.commit()
    return {**line_order_dict(order), 'idempotent': False, 'switched': outcome.get('switched', False)}


@router.post('/{id}/cancel')
def cancel(id: int, data: CancelInput, db=Depends(get_db), u=Depends(admin_only)):
    order, outcome = lines.cancel(db, id, data, u)
    record(db, u.email, 'line.order.cancel',
           {'id': id, 'mode': outcome['mode'], 'reason': data.reason, 'reverse': outcome.get('reverse_order_id')})
    db.commit()
    return {**line_order_dict(order), 'cancel_mode': outcome['mode']}
