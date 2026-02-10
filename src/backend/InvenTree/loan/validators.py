"""Validation methods for the loan app."""


def generate_next_loan_order_reference():
    """Generate the next available LoanOrder reference."""
    from loan.models import LoanOrder

    return LoanOrder.generate_reference()


def validate_loan_order_reference_pattern(pattern):
    """Validate the LoanOrder reference 'pattern' setting."""
    from loan.models import LoanOrder

    LoanOrder.validate_reference_pattern(pattern)


def validate_loan_order_reference(value):
    """Validate that the LoanOrder reference field matches the required pattern."""
    from loan.models import LoanOrder

    LoanOrder.validate_reference_field(value)
