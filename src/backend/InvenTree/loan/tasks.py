"""Background tasks for the loan module."""

import structlog

from django.utils.translation import gettext_lazy as _

from InvenTree.helpers import current_date
from InvenTree.tasks import ScheduledTask, scheduled_task
from plugin.events import trigger_event

logger = structlog.get_logger('inventree')


@scheduled_task(ScheduledTask.DAILY)
def check_overdue_loan_orders():
    """Check for overdue loan orders and trigger events.

    This task runs daily to check for loan orders that have become overdue.
    Overdue is determined by:
    - Order is in OPEN status (PENDING, ISSUED, ON_HOLD)
    - due_date is set and is in the past
    """
    from loan.events import LoanOrderEvents
    from loan.models import LoanOrder

    today = current_date()

    # Find all overdue loan orders
    overdue_orders = LoanOrder.objects.filter(
        LoanOrder.overdue_filter()
    )

    logger.info(f'Found {overdue_orders.count()} overdue loan orders')

    for order in overdue_orders:
        # Trigger overdue event for each order
        trigger_event(
            LoanOrderEvents.OVERDUE,
            id=order.pk,
            reference=order.reference,
            due_date=str(order.due_date),
        )

        logger.debug(
            f'Triggered overdue event for loan order {order.reference}'
        )


@scheduled_task(ScheduledTask.DAILY)
def notify_upcoming_due_dates():
    """Notify responsible users about upcoming due dates.

    This task runs daily to send notifications for loan orders
    that are due within the notification window (e.g., 7 days).
    """
    from datetime import timedelta

    from common.settings import get_global_setting
    from loan.models import LoanOrder
    from loan.status_codes import LoanOrderStatusGroups

    # Get notification window (default 7 days)
    notification_days = get_global_setting(
        'LOANORDER_DUE_DATE_NOTIFICATION_DAYS',
        backup_value=7
    )

    today = current_date()
    notification_date = today + timedelta(days=notification_days)

    # Find orders due within the notification window
    upcoming_orders = LoanOrder.objects.filter(
        status__in=LoanOrderStatusGroups.OPEN,
        due_date__isnull=False,
        due_date__gte=today,
        due_date__lte=notification_date,
    )

    logger.info(
        f'Found {upcoming_orders.count()} loan orders due within {notification_days} days'
    )

    for order in upcoming_orders:
        days_until_due = (order.due_date - today).days

        logger.debug(
            f'Loan order {order.reference} is due in {days_until_due} days'
        )

        # Here you could send notifications to responsible users
        # This would integrate with the InvenTree notification system
