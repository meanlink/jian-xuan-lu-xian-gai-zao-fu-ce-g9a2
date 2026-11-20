"""班组换线单：一张待交接单、双侧交接确认、幂等回执、作废与反向交接。"""
import time
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.models import Job, LineHandover, LineOrder, LineState
from src.services.business import metadata

DEFAULT_LINE = '原线'


def teams():
    for p in metadata().get('parameters', []):
        if p['key'] == 'team':
            return [str(o['value']) for o in p.get('options', []) if str(o['value']) != '全部']
    return []


def current_line(db, team):
    state = db.scalar(select(LineState).where(LineState.team == team))
    return state.current_line if state else DEFAULT_LINE


def ensure_state(db, team):
    state = db.scalar(select(LineState).where(LineState.team == team).with_for_update())
    if state:
        return state
    state = LineState(team=team, current_line=DEFAULT_LINE, updated_at=time.time())
    try:
        # 只回滚这次插入的保存点，避免并发首次开单冲突波及换线单本身
        with db.begin_nested():
            db.add(state)
        return state
    except IntegrityError:
        state = db.scalar(select(LineState).where(LineState.team == team))
        if not state:
            raise
        return state


def _basis_from_job(job, team):
    if job.status != 'completed' or not job.approved:
        raise HTTPException(409, '请选择已完成且获批准的复测结论')
    params_team = str(job.params.get('team', '全部'))
    if params_team not in ('全部', team):
        raise HTTPException(409, f'该结论只覆盖「{params_team}」，不能作为「{team}」的换线依据')
    rows = [r for r in (job.result or {}).get('table', {}).get('rows', []) if r.get('team') == team]
    if not rows:
        raise HTTPException(409, f'该批准结论没有「{team}」的配对样本')
    try:
        avg = sum(float(r['difference']) for r in rows) / len(rows)
    except (KeyError, TypeError, ValueError):
        raise HTTPException(409, '该结论缺少可核对的逐人差值')
    if avg <= 0:
        raise HTTPException(409, f'「{team}」复测平均节省 {avg:.3f} 秒，未显示路线缩短，不能据此换线')
    return {'job_id': job.id, 'job_name': job.name, 'params': job.params,
            'summary': job.result.get('summary', ''), 'team': team,
            'team_avg_saving': round(avg, 4), 'paired_count': len(rows),
            'approved': True}


def create(db, data, user):
    team = str(data.team)
    if team not in teams():
        raise HTTPException(422, '不是有效的试点小组')
    job = db.get(Job, data.job_id)
    if not job:
        raise HTTPException(404, '复测结论不存在')
    basis = _basis_from_job(job, team)
    line = current_line(db, team)
    to_line = str(data.to_line).strip()
    if to_line == line:
        raise HTTPException(409, f'「{team}」当前已在「{line}」，无需换线')
    existing = db.scalar(select(LineOrder).where(LineOrder.pending_team == team))
    if existing:
        raise HTTPException(409, f'「{team}」已有待交接换线单 #{existing.id}，请先完成或作废；相反指令不能同时排队')
    order = LineOrder(team=team, from_line=line, to_line=to_line, job_id=job.id,
                      status='pending', pending_team=team, basis=basis,
                      note=data.note or '', created_by=user.id, created_at=time.time())
    db.add(order)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f'「{team}」已被另一张待交接单占用，请刷新后确认唯一指令')
    return order


def _claim(db, order_id, side, receipt_id, actor, note, occurred_at):
    existing = db.scalar(select(LineHandover).where(LineHandover.receipt_id == receipt_id))
    if existing:
        if existing.order_id != order_id or existing.side != side:
            raise HTTPException(409, '该回执编号已用于另一笔交接，不能复用')
        return existing, True
    order = db.scalar(select(LineOrder).where(LineOrder.id == order_id).with_for_update())
    if not order:
        raise HTTPException(404, '换线单不存在')
    if order.status != 'pending':
        raise HTTPException(409, '单据已结，迟到回执不能改动已生效或已作废的换线单')
    taken = db.scalar(select(LineHandover).where(LineHandover.order_id == order_id, LineHandover.side == side).with_for_update())
    if taken:
        if taken.receipt_id == receipt_id:
            return taken, True
        raise HTTPException(409, '该侧已交接过；重试请使用原回执编号')
    handover = LineHandover(order_id=order_id, side=side,
                            line=order.from_line if side == 'from' else order.to_line,
                            receipt_id=receipt_id, actor=actor, note=note or '',
                            occurred_at=occurred_at, recorded_at=time.time())
    db.add(handover)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        repeat = db.scalar(select(LineHandover).where(LineHandover.receipt_id == receipt_id))
        if repeat:
            return repeat, True
        raise HTTPException(409, '该侧已被另一笔交接占用，请刷新')
    return handover, False


def handover(db, order_id, data, user):
    handover_row, replayed = _claim(db, order_id, data.side, data.receipt_id, user.email,
                                    data.note, data.occurred_at)
    if replayed:
        order = db.get(LineOrder, order_id)
        return order, {'idempotent': True, 'handover_id': handover_row.id}
    order = db.get(LineOrder, order_id)
    sides = {h.side for h in db.scalars(select(LineHandover).where(LineHandover.order_id == order_id).with_for_update())}
    result = {'idempotent': False, 'handover_id': handover_row.id, 'sides': sorted(sides)}
    if 'from' in sides and 'to' in sides:
        _apply(db, order)
        result['switched'] = True
    else:
        result['switched'] = False
    return order, result


def _apply(db, order):
    now = time.time()
    order.status = 'effective'
    order.pending_team = None
    order.effective_at = now
    order.closed_at = now
    state = ensure_state(db, order.team)
    state.current_line = order.to_line
    state.updated_at = now
    state.basis_order_id = order.id
    if order.reverse_of:
        original = db.get(LineOrder, order.reverse_of)
        if original:
            original.status = 'reversed'
            original.closed_at = now


def cancel(db, order_id, data, user):
    order = db.scalar(select(LineOrder).where(LineOrder.id == order_id).with_for_update())
    if not order:
        raise HTTPException(404, '换线单不存在')
    if order.status == 'pending':
        _void(db, order, data.reason, user)
        return order, {'mode': 'voided'}
    if order.status == 'effective':
        reverse = _reverse(db, order, data.reason, user)
        return order, {'mode': 'reverse', 'reverse_order_id': reverse.id}
    if order.status == 'reversing':
        raise HTTPException(409, '该换线单正在反向交接，请撤销对应的反向单')
    raise HTTPException(409, '该换线单已作废或已反向，不能再次撤销')


def _void(db, order, reason, user):
    now = time.time()
    order.status = 'voided'
    order.pending_team = None
    order.cancel_reason = reason
    order.cancelled_by = user.id
    order.cancelled_at = now
    order.closed_at = now
    if order.reverse_of:
        original = db.get(LineOrder, order.reverse_of)
        if original and original.status == 'reversing':
            original.status = 'effective'
            original.reverse_order_id = None
            original.cancel_reason = ''
            original.cancelled_by = None
            original.cancelled_at = None


def _reverse(db, original, reason, user):
    state = ensure_state(db, original.team)
    if state.current_line != original.to_line:
        raise HTTPException(409, f'「{original.team}」当前路线已不是原单目标路线，不能按此单反向交接')
    running = db.scalar(select(LineOrder).where(LineOrder.pending_team == original.team))
    if running:
        raise HTTPException(409, f'「{original.team}」已有待交接换线单 #{running.id}，反向交接不能插队')
    reverse = LineOrder(team=original.team, from_line=original.to_line, to_line=original.from_line,
                        job_id=original.job_id, status='pending', pending_team=original.team,
                        basis={**original.basis, 'reverse_of': original.id, 'cancel_reason': reason},
                        note=f'反向交接：{reason}', created_by=user.id, created_at=time.time(),
                        reverse_of=original.id)
    db.add(reverse)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f'「{original.team}」已有待交接单，反向交接不能插队')
    original.status = 'reversing'
    original.reverse_order_id = reverse.id
    original.cancel_reason = reason
    original.cancelled_by = user.id
    original.cancelled_at = time.time()
    return reverse


def history(db, order_id):
    order = db.scalar(select(LineOrder).where(LineOrder.id == order_id))
    if not order:
        raise HTTPException(404, '换线单不存在')
    chain = [order]
    if order.reverse_of:
        original = db.get(LineOrder, order.reverse_of)
        if original:
            chain.insert(0, original)
    if order.reverse_order_id:
        reverse = db.get(LineOrder, order.reverse_order_id)
        if reverse and reverse not in chain:
            chain.append(reverse)
    return chain


def board(db):
    result = []
    for team in teams():
        state = db.scalar(select(LineState).where(LineState.team == team))
        pending = db.scalar(select(LineOrder).where(LineOrder.pending_team == team))
        effective = db.scalar(select(LineOrder).where(LineOrder.team == team, LineOrder.effective_at.is_not(None)).order_by(LineOrder.effective_at.desc()))
        latest = db.scalar(select(LineOrder).where(LineOrder.team == team).order_by(LineOrder.id.desc()))
        result.append({'team': team, 'current_line': state.current_line if state else DEFAULT_LINE,
                       'updated_at': state.updated_at if state else None,
                       'pending_order': pending, 'effective_order': effective, 'latest_order': latest})
    return result
