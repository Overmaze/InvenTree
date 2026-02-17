"""Loan status codes."""

from django.utils.translation import gettext_lazy as _

from generic.states import ColorEnum, StatusCode


class LoanOrderStatus(StatusCode):
    """Defines a set of status codes for a LoanOrder.

    Note: OVERDUE is NOT a status - it's a computed property based on
    due_date and whether the order is still OPEN.
    """

    # Order is pending, not yet issued
    PENDING = 10, _('Pending'), ColorEnum.secondary

    # Order has been approved by supervisor (requires permission)
    APPROVED = 15, _('Approved'), ColorEnum.success

    # Order has been issued, items are out on loan
    ISSUED = 20, _('Issued'), ColorEnum.primary

    # Items have been shipped out to borrower
    SHIPPED = 22, _('Shipped'), ColorEnum.info

    # Order is on hold
    ON_HOLD = 25, _('On Hold'), ColorEnum.warning

    # All items have been returned
    RETURNED = 30, _('Returned'), ColorEnum.success

    # Some items returned, some still on loan
    PARTIAL_RETURN = 35, _('Partially Returned'), ColorEnum.warning

    # Loan has been converted to a sale
    CONVERTED_TO_SALE = 40, _('Converted to Sale'), ColorEnum.info

    # Order was cancelled
    CANCELLED = 50, _('Cancelled'), ColorEnum.danger

    # Items were lost/damaged and written off
    WRITTEN_OFF = 60, _('Written Off'), ColorEnum.dark


class LoanOrderStatusGroups:
    """Groups for LoanOrderStatus codes."""

    # Open orders (items still out on loan or awaiting issue)
    OPEN = [
        LoanOrderStatus.PENDING.value,
        LoanOrderStatus.APPROVED.value,
        LoanOrderStatus.ISSUED.value,
        LoanOrderStatus.SHIPPED.value,
        LoanOrderStatus.ON_HOLD.value,
        LoanOrderStatus.PARTIAL_RETURN.value,
    ]

    # Completed orders
    COMPLETE = [
        LoanOrderStatus.RETURNED.value,
        LoanOrderStatus.CONVERTED_TO_SALE.value,
    ]

    # Failed/terminated orders
    FAILED = [
        LoanOrderStatus.CANCELLED.value,
        LoanOrderStatus.WRITTEN_OFF.value,
    ]


class LoanOrderLineStatus(StatusCode):
    """Defines a set of status codes for a LoanOrderLineItem."""

    # Item is pending (not yet shipped)
    PENDING = 10, _('Pending'), ColorEnum.secondary

    # Item has been shipped out on loan
    SHIPPED = 20, _('Shipped'), ColorEnum.primary

    # Item has been returned
    RETURNED = 30, _('Returned'), ColorEnum.success

    # Item has been converted to sale
    CONVERTED_TO_SALE = 40, _('Converted to Sale'), ColorEnum.info

    # Item is partially converted (some qty converted, some still on loan)
    PARTIALLY_CONVERTED = 45, _('Partially Converted'), ColorEnum.warning

    # Item was lost
    LOST = 50, _('Lost'), ColorEnum.danger

    # Item was damaged
    DAMAGED = 60, _('Damaged'), ColorEnum.warning


class LoanOrderLineStatusGroups:
    """Groups for LoanOrderLineStatus codes."""

    # Items currently out on loan
    OUT_ON_LOAN = [
        LoanOrderLineStatus.SHIPPED.value,
        LoanOrderLineStatus.PARTIALLY_CONVERTED.value,
    ]

    # Completed line items
    COMPLETE = [
        LoanOrderLineStatus.RETURNED.value,
        LoanOrderLineStatus.CONVERTED_TO_SALE.value,
    ]

    # Problem line items
    PROBLEM = [
        LoanOrderLineStatus.LOST.value,
        LoanOrderLineStatus.DAMAGED.value,
    ]
