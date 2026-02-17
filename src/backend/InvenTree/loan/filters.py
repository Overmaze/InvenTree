"""Custom filters for the loan app."""

from django.db.models import Q

from loan.status_codes import LoanOrderStatusGroups


def filter_open_loan_orders():
    """Return a Q filter for open loan orders."""
    return Q(status__in=LoanOrderStatusGroups.OPEN)


def filter_completed_loan_orders():
    """Return a Q filter for completed loan orders."""
    return Q(status__in=LoanOrderStatusGroups.COMPLETE)


def filter_failed_loan_orders():
    """Return a Q filter for failed loan orders."""
    return Q(status__in=LoanOrderStatusGroups.FAILED)
