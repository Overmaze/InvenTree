"""Background tasks for the loan module."""

from datetime import timedelta

import structlog

from django.utils.translation import gettext_lazy as _

import InvenTree.helpers_model
import common.notifications
from InvenTree.helpers import current_date
from InvenTree.tasks import ScheduledTask, scheduled_task
from plugin.events import trigger_event

logger = structlog.get_logger('inventree')


def notify_overdue_loan_order(order) -> None:
    """Notify users that a LoanOrder has just become overdue.

    Arguments:
        order: The LoanOrder object that is overdue.
    """
    from loan.events import LoanOrderEvents

    targets = []

    if order.created_by:
        targets.append(order.created_by)

    if order.responsible:
        targets.append(order.responsible)

    targets.extend(order.subscribed_users())

    name = _('Overdue Loan Order')

    context = {
        'order': order,
        'name': name,
        'message': _(f'Loan order {order} is now overdue'),
        'link': InvenTree.helpers_model.construct_absolute_url(order.get_absolute_url()),
        'template': {'html': 'email/overdue_loan_order.html', 'subject': name},
    }

    event_name = LoanOrderEvents.OVERDUE

    common.notifications.trigger_notification(
        order, event_name, targets=targets, context=context
    )

    trigger_event(event_name, loan_order=order.pk)


@scheduled_task(ScheduledTask.DAILY)
def check_overdue_loan_orders():
    """Check for overdue loan orders and trigger notifications.

    This task runs daily. It checks for loan orders where:
    - Order is in OPEN status
    - due_date expired *yesterday* (just became overdue)

    This follows the same pattern as PurchaseOrder/SalesOrder overdue checks.
    """
    from loan.models import LoanOrder
    from loan.status_codes import LoanOrderStatusGroups

    yesterday = current_date() - timedelta(days=1)

    # Find orders that just became overdue yesterday
    overdue_orders = LoanOrder.objects.filter(
        due_date=yesterday,
        status__in=LoanOrderStatusGroups.OPEN,
    )

    logger.info(f'Found {overdue_orders.count()} newly overdue loan orders')

    for order in overdue_orders:
        notify_overdue_loan_order(order)
        logger.debug(f'Notified overdue for loan order {order.reference}')


@scheduled_task(ScheduledTask.DAILY)
def notify_upcoming_due_dates():
    """Notify responsible users about upcoming due dates.

    This task runs daily to send notifications for loan orders
    that are due within the notification window (default 7 days).
    """
    from common.settings import get_global_setting
    from loan.events import LoanOrderEvents
    from loan.models import LoanOrder
    from loan.status_codes import LoanOrderStatusGroups

    notification_days = get_global_setting(
        'LOANORDER_DUE_DATE_NOTIFICATION_DAYS',
        backup_value=7
    )

    today = current_date()
    notification_date = today + timedelta(days=notification_days)

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

        targets = []
        if order.created_by:
            targets.append(order.created_by)
        if order.responsible:
            targets.append(order.responsible)
        targets.extend(order.subscribed_users())

        name = _('Upcoming Loan Due Date')
        context = {
            'order': order,
            'name': name,
            'message': _(f'Loan order {order} is due in {days_until_due} days'),
            'link': InvenTree.helpers_model.construct_absolute_url(order.get_absolute_url()),
            'template': {'html': 'email/upcoming_loan_due.html', 'subject': name},
        }

        common.notifications.trigger_notification(
            order, LoanOrderEvents.DUE_SOON, targets=targets, context=context
        )

        logger.debug(
            f'Loan order {order.reference} is due in {days_until_due} days'
        )
