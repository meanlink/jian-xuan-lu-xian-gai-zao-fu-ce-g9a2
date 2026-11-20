from sqlalchemy import String, Double, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base


class LineOrder(Base):
    """班组换线单。pending 期间原线继续生效，两侧交接确认后才切换。"""
    __tablename__ = 'line_orders'
    id: Mapped[int] = mapped_column(primary_key=True)
    team: Mapped[str] = mapped_column(String(40), index=True)
    from_line: Mapped[str] = mapped_column(String(40))
    to_line: Mapped[str] = mapped_column(String(40))
    job_id: Mapped[int] = mapped_column(ForeignKey('jobs.id'))
    status: Mapped[str] = mapped_column(String(20), default='pending', index=True)
    # 仅待交接单占用该列；唯一索引保证同组最多一张待交接单，已结单据置空。
    pending_team: Mapped[str | None] = mapped_column(String(40), nullable=True, unique=True)
    basis: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str] = mapped_column(String(300), default='')
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
    effective_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    closed_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    cancel_reason: Mapped[str] = mapped_column(String(300), default='')
    cancelled_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    cancelled_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    reverse_of: Mapped[int | None] = mapped_column(ForeignKey('line_orders.id'), nullable=True)
    reverse_order_id: Mapped[int | None] = mapped_column(ForeignKey('line_orders.id'), nullable=True)


class LineHandover(Base):
    """交接回执。receipt_id 为幂等键，同一回执重试只生效一次。"""
    __tablename__ = 'line_handovers'
    __table_args__ = (UniqueConstraint('order_id', 'side', name='uq_line_handover_side'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('line_orders.id'), index=True)
    side: Mapped[str] = mapped_column(String(10))
    receipt_id: Mapped[str] = mapped_column(String(80), unique=True)
    line: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(150))
    note: Mapped[str] = mapped_column(String(300), default='')
    occurred_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    recorded_at: Mapped[float] = mapped_column(Double)


class LineState(Base):
    """班组当前路线。只有换线单生效时才更新。"""
    __tablename__ = 'line_states'
    id: Mapped[int] = mapped_column(primary_key=True)
    team: Mapped[str] = mapped_column(String(40), unique=True)
    current_line: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[float] = mapped_column(Double)
    basis_order_id: Mapped[int | None] = mapped_column(ForeignKey('line_orders.id'), nullable=True)
