"""
Order Event Model

Tracks activity history for sales orders - status changes, notes, payments, etc.
Provides an audit trail and activity timeline for the OrderDetail page.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import backref, relationship
from datetime import datetime, timezone

from app.db.base import Base


class OrderEvent(Base):
    """Order Event - Activity log entry for a sales order"""
    __tablename__ = "order_events"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Foreign Keys
    sales_order_id = Column(
        Integer,
        ForeignKey("sales_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    # Note: ondelete=NO ACTION to avoid multiple cascade paths
    # (sales_order->user and order_event->user)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=True,
        index=True
    )

    # Event Type
    # status_change, note_added, payment_received, payment_refunded,
    # production_started, production_completed, shipped, delivered,
    # address_updated, cancelled, on_hold, resumed
    event_type = Column(String(50), nullable=False, index=True)

    # Event Details
    title = Column(String(255), nullable=False)  # Short description
    description = Column(Text, nullable=True)  # Detailed description

    # For status changes
    old_value = Column(String(100), nullable=True)  # Previous status
    new_value = Column(String(100), nullable=True)  # New status

    # Metadata (JSON-like key=value for additional context)
    # Examples: payment_amount=150.00, tracking_number=1Z999AA10123456784
    metadata_key = Column(String(100), nullable=True)
    metadata_value = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    # passive_deletes: al borrar el pedido, la FK (ondelete=CASCADE) borra estas filas
    # en la BD. Sin esto SQLAlchemy intenta poner sales_order_id a NULL antes de
    # borrar el pedido y choca con nullable=False (fallaba "Eliminar pedido").
    sales_order = relationship("SalesOrder", backref=backref("events", passive_deletes=True))
    user = relationship("User")

    def __repr__(self):
        return f"<OrderEvent {self.event_type} for SO-{self.sales_order_id}>"
