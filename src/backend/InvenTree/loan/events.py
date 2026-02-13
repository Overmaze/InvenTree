"""Event definitions for the loan app."""

from generic.events import BaseEventEnum


class LoanOrderEvents(BaseEventEnum):
    """Event definitions for LoanOrder model."""

    # Loan order lifecycle events
    CREATED = 'loanorder.created'
    APPROVED = 'loanorder.approved'
    ISSUED = 'loanorder.issued'
    SHIPPED = 'loanorder.shipped'
    RETURNED = 'loanorder.returned'
    PARTIAL_RETURN = 'loanorder.partial_return'
    CONVERTED = 'loanorder.converted_to_sale'
    CANCELLED = 'loanorder.cancelled'
    ON_HOLD = 'loanorder.on_hold'
    WRITTEN_OFF = 'loanorder.written_off'

    # Special events
    OVERDUE = 'loanorder.overdue'  # Triggered by scheduled task, not status change

    # Line item events
    LINE_ITEM_SHIPPED = 'loanorder.line_item_shipped'
    LINE_ITEM_RETURNED = 'loanorder.line_item_returned'
    LINE_ITEM_CONVERTED = 'loanorder.line_item_converted'
    LINE_ITEM_LOST = 'loanorder.line_item_lost'
    LINE_ITEM_DAMAGED = 'loanorder.line_item_damaged'
