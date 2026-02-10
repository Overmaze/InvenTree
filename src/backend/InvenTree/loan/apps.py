"""App configuration for the loan module."""

from django.apps import AppConfig


class LoanConfig(AppConfig):
    """Configuration class for the 'loan' app."""

    name = 'loan'
    verbose_name = 'Loan Management'

    def ready(self):
        """Initialize the loan app when Django starts."""
        # Import signals if needed
        pass
