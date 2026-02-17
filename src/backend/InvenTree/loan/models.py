"""Loan order model definitions."""

from decimal import Decimal
from typing import Any, Optional

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F, Q, QuerySet, Sum
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

import structlog
from djmoney.contrib.exchange.exceptions import MissingRate
from djmoney.contrib.exchange.models import convert_money
from djmoney.money import Money

import common.models as common_models
import InvenTree.helpers
import InvenTree.models
import InvenTree.validators
import loan.validators
import report.mixins
import stock.models
import users.models as UserModels
from common.currency import currency_code_default
from common.notifications import InvenTreeNotificationBodies
from common.settings import get_global_setting
from company.models import Address, Company, Contact
from generic.states import StateTransitionMixin, StatusCodeMixin
from generic.states.fields import InvenTreeCustomStatusModelField
from InvenTree.exceptions import log_error
from InvenTree.fields import (
    InvenTreeModelMoneyField,
    InvenTreeURLField,
    RoundingDecimalField,
)
from InvenTree.helpers import decimal2string, pui_url
from InvenTree.helpers_model import notify_responsible
from loan.events import LoanOrderEvents
from loan.status_codes import (
    LoanOrderLineStatus,
    LoanOrderLineStatusGroups,
    LoanOrderStatus,
    LoanOrderStatusGroups,
)
from part import models as PartModels
from plugin.events import trigger_event
from stock.status_codes import StockHistoryCode, StockStatus

logger = structlog.get_logger('inventree')


# Allowed status transitions for LoanOrder
ALLOWED_TRANSITIONS = {
    LoanOrderStatus.PENDING.value: [
        LoanOrderStatus.APPROVED.value,
        LoanOrderStatus.ISSUED.value,  # Direct issue without approval
        LoanOrderStatus.ON_HOLD.value,
        LoanOrderStatus.CANCELLED.value,
    ],
    LoanOrderStatus.APPROVED.value: [
        LoanOrderStatus.ISSUED.value,
        LoanOrderStatus.ON_HOLD.value,
        LoanOrderStatus.CANCELLED.value,
    ],
    LoanOrderStatus.ISSUED.value: [
        LoanOrderStatus.SHIPPED.value,  # Auto-transition when items are shipped
        LoanOrderStatus.ON_HOLD.value,
        LoanOrderStatus.PARTIAL_RETURN.value,
        LoanOrderStatus.RETURNED.value,
        LoanOrderStatus.CONVERTED_TO_SALE.value,
        LoanOrderStatus.WRITTEN_OFF.value,
    ],
    LoanOrderStatus.SHIPPED.value: [
        LoanOrderStatus.ON_HOLD.value,
        LoanOrderStatus.PARTIAL_RETURN.value,
        LoanOrderStatus.RETURNED.value,
        LoanOrderStatus.CONVERTED_TO_SALE.value,
        LoanOrderStatus.WRITTEN_OFF.value,
    ],
    LoanOrderStatus.ON_HOLD.value: [
        LoanOrderStatus.PENDING.value,
        LoanOrderStatus.APPROVED.value,
        LoanOrderStatus.ISSUED.value,
        LoanOrderStatus.SHIPPED.value,  # Resume to shipped if items were previously shipped
        LoanOrderStatus.CANCELLED.value,
    ],
    LoanOrderStatus.PARTIAL_RETURN.value: [
        LoanOrderStatus.RETURNED.value,
        LoanOrderStatus.CONVERTED_TO_SALE.value,
        LoanOrderStatus.WRITTEN_OFF.value,
    ],
    LoanOrderStatus.RETURNED.value: [
        LoanOrderStatus.CONVERTED_TO_SALE.value,  # Can sell returned items
    ],
    LoanOrderStatus.CONVERTED_TO_SALE.value: [],  # Terminal state
    LoanOrderStatus.CANCELLED.value: [],  # Terminal state
    LoanOrderStatus.WRITTEN_OFF.value: [],  # Terminal state
}


class TotalPriceMixin(models.Model):
    """Mixin which provides 'total_price' field for an order."""

    class Meta:
        """Meta for TotalPriceMixin."""

        abstract = True

    def save(self, *args, **kwargs):
        """Update the total_price field when saved."""
        # Recalculate total_price for this order
        self.update_total_price(commit=False)

        if hasattr(self, '_SAVING_TOTAL_PRICE') and self._SAVING_TOTAL_PRICE:
            # Avoid recursion on save
            return super().save(*args, **kwargs)
        self._SAVING_TOTAL_PRICE = True

        # Save the object as we can not access foreign/m2m fields before saving
        self.update_total_price(commit=True)

    total_price = InvenTreeModelMoneyField(
        null=True,
        blank=True,
        allow_negative=False,
        verbose_name=_('Total Price'),
        help_text=_('Total price for this order'),
    )

    order_currency = models.CharField(
        max_length=3,
        verbose_name=_('Order Currency'),
        blank=True,
        null=True,
        help_text=_('Currency for this order (leave blank to use company default)'),
        validators=[InvenTree.validators.validate_currency_code],
    )

    @property
    def currency(self):
        """Return the currency associated with this order instance."""
        if self.order_currency:
            return self.order_currency

        if self.borrower_company:
            return self.borrower_company.currency_code

        return currency_code_default()

    def update_total_price(self, commit=True):
        """Recalculate and save the total_price for this order."""
        self.total_price = self.calculate_total_price(target_currency=self.currency)

        if commit:
            self.save()

    def calculate_total_price(self, target_currency=None):
        """Calculate the total price of all order lines."""
        if target_currency is None:
            target_currency = currency_code_default()

        total = Money(0, target_currency)

        if self.pk is None:
            return total

        # Line items
        for line in self.lines.all():
            if not line.price:
                continue

            try:
                total += line.quantity * convert_money(line.price, target_currency)
            except MissingRate:
                log_error('loan.calculate_total_price')
                logger.exception("Missing exchange rate for '%s'", target_currency)
                return None

        # Extra lines (deposits, fees, etc.)
        for line in self.extra_lines.all():
            if not line.price:
                continue

            try:
                total += line.quantity * convert_money(line.price, target_currency)
            except MissingRate:
                log_error('loan.calculate_total_price')
                logger.exception("Missing exchange rate for '%s'", target_currency)
                return None

        total.decimal_places = 4
        return total


class LoanOrderReportContext(report.mixins.BaseReportContext):
    """Context for the loan order model.

    Attributes:
        description: The description field of the LoanOrder
        reference: The reference field of the LoanOrder
        title: The title (string representation) of the LoanOrder
        extra_lines: Query set of all extra lines associated with the LoanOrder
        lines: Query set of all line items associated with the LoanOrder
        order: The LoanOrder instance itself
        borrower_company: The borrower company associated with the LoanOrder
        due_date: The due date for returning the loan
        is_overdue: Whether the loan is overdue
    """

    description: str
    reference: str
    title: str
    extra_lines: report.mixins.QuerySet['LoanOrderExtraLine']
    lines: report.mixins.QuerySet['LoanOrderLineItem']
    order: 'LoanOrder'
    borrower_company: Optional[Company]
    due_date: Any
    is_overdue: bool


class LoanOrder(
    TotalPriceMixin,
    StatusCodeMixin,
    StateTransitionMixin,
    InvenTree.models.InvenTreeParameterMixin,
    InvenTree.models.InvenTreeAttachmentMixin,
    InvenTree.models.InvenTreeBarcodeMixin,
    InvenTree.models.InvenTreeNotesMixin,
    report.mixins.InvenTreeReportMixin,
    InvenTree.models.MetadataMixin,
    InvenTree.models.ReferenceIndexingMixin,
    InvenTree.models.InvenTreeModel,
):
    """A LoanOrder represents items loaned out to a customer temporarily.

    Items on loan are tracked and expected to be returned by a due date.
    Loans can be converted to sales if the customer decides to keep items.

    Attributes:
        reference: Unique order number / reference / code
        description: Long form description
        borrower_company: Company borrowing the items (must be a customer)
        responsible: User or group responsible for this loan
        contact: Point of contact at the borrower company
        address: Shipping address for the loan
        creation_date: Date the loan order was created
        created_by: User who created the order
        issue_date: Date the loan was issued (items shipped out)
        due_date: Expected return date for loaned items
        return_date: Actual date items were returned
        target_date: Target date for completion (alias for due_date in reports)
        notes: Additional notes
    """

    REFERENCE_PATTERN_SETTING = 'LOANORDER_REFERENCE_PATTERN'
    REQUIRE_RESPONSIBLE_SETTING = 'LOANORDER_REQUIRE_RESPONSIBLE'
    STATUS_CLASS = LoanOrderStatus
    UNLOCK_SETTING = 'LOANORDER_EDIT_COMPLETED_ORDERS'

    class Meta:
        """Model meta options."""

        verbose_name = _('Loan Order')
        verbose_name_plural = _('Loan Orders')

    def __str__(self):
        """Render a string representation of this LoanOrder."""
        borrower = self.borrower_company.name if self.borrower_company else _('deleted')
        return f'{self.reference} - {borrower}'

    def save(self, *args, **kwargs):
        """Custom save method for LoanOrder."""
        update = self.pk is not None

        # Locking check
        if update and self.check_locked(True):
            if self.get_db_instance().status != self.status:
                pass
            else:
                raise ValidationError({
                    'reference': _('This order is locked and cannot be modified')
                })

        # Reference calculations
        self.reference_int = self.rebuild_reference_field(self.reference)
        if not self.creation_date:
            self.creation_date = InvenTree.helpers.current_date()

        super().save(*args, **kwargs)

    def check_locked(self, db: bool = False) -> bool:
        """Check if this order is 'locked'."""
        if not self.check_complete(db=db):
            return False

        if self.UNLOCK_SETTING:
            return get_global_setting(self.UNLOCK_SETTING, backup_value=False) is False

        return False

    def check_complete(self, db: bool = False) -> bool:
        """Check if this order is 'complete'."""
        status = self.get_db_instance().status if db else self.status
        return status in LoanOrderStatusGroups.COMPLETE + LoanOrderStatusGroups.FAILED

    def clean(self):
        """Custom clean method for LoanOrder."""
        super().clean()

        # Check if responsible owner is required
        if self.REQUIRE_RESPONSIBLE_SETTING:
            if get_global_setting(self.REQUIRE_RESPONSIBLE_SETTING, backup_value=False):
                if not self.responsible:
                    raise ValidationError({
                        'responsible': _('Responsible user or group must be specified')
                    })

        # Validate borrower_company is a customer
        if self.borrower_company and not self.borrower_company.is_customer:
            raise ValidationError({
                'borrower_company': _('Selected company is not a customer')
            })

        # Contact must belong to borrower company
        if self.borrower_company and self.contact:
            if self.contact.company != self.borrower_company:
                raise ValidationError({
                    'contact': _('Contact does not match selected company')
                })

        # Address must belong to borrower company
        if self.borrower_company and self.address:
            if self.address.company != self.borrower_company:
                raise ValidationError({
                    'address': _('Address does not match selected company')
                })

        # Issue date should not be before creation date
        if self.issue_date and self.creation_date and self.issue_date < self.creation_date:
            raise ValidationError({
                'issue_date': _('Issue date cannot be before creation date'),
            })

        # Due date should be after issue date
        if self.issue_date and self.due_date and self.issue_date > self.due_date:
            raise ValidationError({
                'due_date': _('Due date must be after issue date'),
                'issue_date': _('Issue date must be before due date'),
            })

        # Due date should be after creation date
        if self.due_date and self.creation_date and self.due_date < self.creation_date:
            raise ValidationError({
                'due_date': _('Due date cannot be before creation date'),
            })

        # Return date should be after issue date
        if self.return_date and self.issue_date and self.return_date < self.issue_date:
            raise ValidationError({
                'return_date': _('Return date cannot be before issue date'),
            })

        # Ship date should be after issue date
        if self.ship_date and self.issue_date and self.ship_date < self.issue_date:
            raise ValidationError({
                'ship_date': _('Ship date cannot be before issue date'),
            })

    def report_context(self) -> LoanOrderReportContext:
        """Generate context data for the reporting interface."""
        return {
            'description': self.description,
            'extra_lines': self.extra_lines,
            'lines': self.lines,
            'order': self,
            'reference': self.reference,
            'title': str(self),
            'borrower_company': self.borrower_company,
            'due_date': self.due_date,
            'is_overdue': self.is_overdue,
        }

    def get_absolute_url(self) -> str:
        """Get the 'web' URL for this order."""
        return pui_url(f'/loan/loan-order/{self.pk}')

    @staticmethod
    def get_api_url() -> str:
        """Return the API URL associated with the LoanOrder model."""
        return reverse('api-loan-order-list')

    @classmethod
    def get_status_class(cls):
        """Return the LoanOrderStatusGroups class."""
        return LoanOrderStatusGroups

    @classmethod
    def api_defaults(cls, request=None) -> dict:
        """Return default values for API OPTIONS request."""
        return {'reference': loan.validators.generate_next_loan_order_reference()}

    @classmethod
    def barcode_model_type_code(cls) -> str:
        """Return the barcode model type code."""
        return 'LO'

    @classmethod
    def overdue_filter(cls):
        """Return a Q filter for overdue loan orders.

        OVERDUE is NOT a status - it's computed from:
        - Order is in OPEN status (PENDING, ISSUED, or ON_HOLD)
        - due_date is set and is in the past
        """
        today = InvenTree.helpers.current_date()
        return (
            Q(status__in=LoanOrderStatusGroups.OPEN)
            & ~Q(due_date=None)
            & Q(due_date__lt=today)
        )

    @property
    def is_overdue(self) -> bool:
        """Computed property to check if this loan is overdue.

        Returns True if:
        - The order is in an OPEN state (PENDING, ISSUED, ON_HOLD)
        - The due_date has passed
        """
        return (
            self.__class__.objects.filter(pk=self.pk)
            .filter(self.__class__.overdue_filter())
            .exists()
        )

    @property
    def target_date(self):
        """Alias for due_date for compatibility with Order base patterns."""
        return self.due_date

    @property
    def company(self):
        """Accessor helper for compatibility with Order patterns."""
        return self.borrower_company

    # Fields
    reference = models.CharField(
        unique=True,
        max_length=64,
        blank=False,
        verbose_name=_('Reference'),
        help_text=_('Loan order reference'),
        default=loan.validators.generate_next_loan_order_reference,
        validators=[loan.validators.validate_loan_order_reference],
    )

    status = InvenTreeCustomStatusModelField(
        default=LoanOrderStatus.PENDING.value,
        choices=LoanOrderStatus.items(),
        status_class=LoanOrderStatus,
        verbose_name=_('Status'),
        help_text=_('Loan order status'),
    )

    @property
    def status_text(self):
        """Return the text representation of the status field."""
        return LoanOrderStatus.text(self.status)

    description = models.CharField(
        max_length=250,
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Loan order description (optional)'),
    )

    # CRITICAL: borrower_company is separate from 'owner'
    # Owner can only point to User or Group, not Company
    borrower_company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={'is_customer': True},
        related_name='loan_orders',
        verbose_name=_('Borrower'),
        help_text=_('Company borrowing the items'),
    )

    responsible = models.ForeignKey(
        UserModels.Owner,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text=_('User or group responsible for this loan order'),
        verbose_name=_('Responsible'),
        related_name='+',
    )

    contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_('Contact'),
        help_text=_('Point of contact for this loan'),
        related_name='+',
    )

    address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_('Address'),
        help_text=_('Shipping address for loaned items'),
        related_name='+',
    )

    project_code = models.ForeignKey(
        common_models.ProjectCode,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_('Project Code'),
        help_text=_('Select project code for this loan order'),
    )

    link = InvenTreeURLField(
        blank=True,
        verbose_name=_('Link'),
        help_text=_('Link to external page'),
        max_length=2000,
    )

    creation_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Creation Date'),
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='+',
        verbose_name=_('Created By'),
    )

    issue_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Issue Date'),
        help_text=_('Date loan was issued'),
    )

    due_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Due Date'),
        help_text=_('Expected return date for loaned items'),
    )

    ship_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Ship Date'),
        help_text=_('Date items were shipped to borrower'),
    )

    return_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Return Date'),
        help_text=_('Actual date items were returned'),
    )

    # Related SalesOrder if loan was converted
    converted_sales_order = models.ForeignKey(
        'order.SalesOrder',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='converted_from_loan',
        verbose_name=_('Converted Sales Order'),
        help_text=_('Sales order created when loan was converted to sale'),
    )

    def subscribed_users(self) -> list[User]:
        """Return a list of users subscribed to this LoanOrder."""
        subscribed_users = set()

        for line in self.lines.all():
            if line.part:
                for user in line.part.get_subscribers():
                    subscribed_users.add(user)

        return list(subscribed_users)

    # region Properties

    @property
    def is_pending(self) -> bool:
        """Return True if the LoanOrder is 'pending'."""
        return self.status == LoanOrderStatus.PENDING.value

    @property
    def is_open(self) -> bool:
        """Return True if the LoanOrder is 'open' (items still out on loan)."""
        return self.status in LoanOrderStatusGroups.OPEN

    @property
    def is_issued(self) -> bool:
        """Return True if the LoanOrder has been issued."""
        return self.status == LoanOrderStatus.ISSUED.value

    @property
    def is_shipped(self) -> bool:
        """Return True if the LoanOrder has items shipped."""
        return self.status == LoanOrderStatus.SHIPPED.value

    @property
    def line_count(self) -> int:
        """Return the total number of line items."""
        return self.lines.count()

    @property
    def completed_line_count(self) -> int:
        """Return the number of completed line items."""
        return self.completed_line_items().count()

    @property
    def pending_line_count(self) -> int:
        """Return the number of pending line items."""
        return self.pending_line_items().count()

    # endregion

    # region Line Item Queries

    def pending_line_items(self) -> QuerySet:
        """Return line items that are still pending (not yet fully returned)."""
        return self.lines.exclude(
            status__in=LoanOrderLineStatusGroups.COMPLETE + LoanOrderLineStatusGroups.PROBLEM
        )

    def completed_line_items(self) -> QuerySet:
        """Return line items that have been completed (returned or converted)."""
        return self.lines.filter(status__in=LoanOrderLineStatusGroups.COMPLETE)

    def shipped_line_items(self) -> QuerySet:
        """Return line items that have been shipped out on loan."""
        return self.lines.filter(status__in=LoanOrderLineStatusGroups.OUT_ON_LOAN)

    # endregion

    # region State Transition Methods

    @property
    def can_approve(self) -> bool:
        """Check if this loan can be approved."""
        return self.status == LoanOrderStatus.PENDING.value

    @property
    def can_issue(self) -> bool:
        """Check if this loan can be issued."""
        return self.status in [
            LoanOrderStatus.PENDING.value,
            LoanOrderStatus.APPROVED.value,
            LoanOrderStatus.ON_HOLD.value,
        ]

    @property
    def can_cancel(self) -> bool:
        """Check if this loan can be cancelled."""
        return self.status in [
            LoanOrderStatus.PENDING.value,
            LoanOrderStatus.ON_HOLD.value,
        ]

    @property
    def can_hold(self) -> bool:
        """Check if this loan can be placed on hold."""
        return self.status in [
            LoanOrderStatus.PENDING.value,
            LoanOrderStatus.ISSUED.value,
            LoanOrderStatus.SHIPPED.value,
        ]

    @property
    def can_return(self) -> bool:
        """Check if this loan can be marked as returned.

        Requires that at least some items have been shipped.
        """
        if self.status not in [
            LoanOrderStatus.ISSUED.value,
            LoanOrderStatus.SHIPPED.value,
            LoanOrderStatus.PARTIAL_RETURN.value,
        ]:
            return False

        # Must have at least some shipped items to return
        return self.lines.filter(shipped__gt=0).exists()

    @property
    def can_convert_to_sale(self) -> bool:
        """Check if this loan can be converted to a sale.

        Requires that at least some items have been shipped.
        """
        if self.status not in [
            LoanOrderStatus.ISSUED.value,
            LoanOrderStatus.SHIPPED.value,
            LoanOrderStatus.PARTIAL_RETURN.value,
        ]:
            return False

        return self.lines.filter(shipped__gt=0).exists()

    @property
    def can_write_off(self) -> bool:
        """Check if this loan can be written off.

        Requires that at least some items have been shipped.
        """
        if self.status not in [
            LoanOrderStatus.ISSUED.value,
            LoanOrderStatus.SHIPPED.value,
            LoanOrderStatus.PARTIAL_RETURN.value,
        ]:
            return False

        return self.lines.filter(shipped__gt=0).exists()

    def _validate_transition(self, target_status: int) -> bool:
        """Validate that a status transition is allowed."""
        allowed = ALLOWED_TRANSITIONS.get(self.status, [])
        return target_status in allowed

    def _action_approve(self, *args, **kwargs):
        """Mark the LoanOrder as APPROVED."""
        if self.can_approve:
            self.status = LoanOrderStatus.APPROVED.value
            self.save()

            trigger_event(LoanOrderEvents.APPROVED, id=self.pk)

            notify_responsible(
                self,
                LoanOrder,
                exclude=self.created_by,
                content=InvenTreeNotificationBodies.NewOrder,
                extra_users=self.subscribed_users(),
            )

    def _action_issue(self, *args, **kwargs):
        """Mark the LoanOrder as ISSUED (or SHIPPED if items were already shipped)."""
        if self.can_issue:
            # If resuming from ON_HOLD with previously shipped items, go to SHIPPED
            has_shipped = self.lines.filter(
                status=LoanOrderLineStatus.SHIPPED.value
            ).exists()
            if has_shipped:
                self.status = LoanOrderStatus.SHIPPED.value
            else:
                self.status = LoanOrderStatus.ISSUED.value
            self.issue_date = self.issue_date or InvenTree.helpers.current_date()
            self.save()

            trigger_event(LoanOrderEvents.ISSUED, id=self.pk)

            notify_responsible(
                self,
                LoanOrder,
                exclude=self.created_by,
                content=InvenTreeNotificationBodies.NewOrder,
                extra_users=self.subscribed_users(),
            )

    def _action_hold(self, *args, **kwargs):
        """Mark the LoanOrder as ON_HOLD."""
        if self.can_hold:
            self.status = LoanOrderStatus.ON_HOLD.value
            self.save()

            trigger_event(LoanOrderEvents.ON_HOLD, id=self.pk)

    def _action_cancel(self, *args, **kwargs):
        """Mark the LoanOrder as CANCELLED."""
        if self.can_cancel:
            self.status = LoanOrderStatus.CANCELLED.value
            self.save()

            trigger_event(LoanOrderEvents.CANCELLED, id=self.pk)

            notify_responsible(
                self,
                LoanOrder,
                exclude=self.created_by,
                content=InvenTreeNotificationBodies.OrderCanceled,
                extra_users=self.subscribed_users(),
            )

    def _action_return(self, *args, **kwargs):
        """Mark the LoanOrder as RETURNED, cascading to all line items."""
        if self.can_return:
            # Update all shipped line items to RETURNED
            for line in self.lines.exclude(
                status__in=LoanOrderLineStatusGroups.COMPLETE
                + LoanOrderLineStatusGroups.PROBLEM
            ):
                # Only return line items that have actually been shipped
                if line.shipped > 0:
                    if line.shipped > line.returned:
                        line.returned = line.shipped
                    line.status = LoanOrderLineStatus.RETURNED.value
                    line.save(update_order=False)

                    # Process allocations: mark them as fully returned
                    for alloc in line.allocations.filter(quantity__gt=0):
                        remaining = alloc.quantity - alloc.returned
                        if remaining > 0:
                            alloc.returned += remaining
                            alloc.quantity = 0
                            alloc.save()

            self.status = LoanOrderStatus.RETURNED.value
            self.return_date = InvenTree.helpers.current_date()
            self.save()

            trigger_event(LoanOrderEvents.RETURNED, id=self.pk)

    def _action_convert(self, *args, **kwargs):
        """Mark the LoanOrder as CONVERTED_TO_SALE."""
        if self.can_convert_to_sale:
            self.status = LoanOrderStatus.CONVERTED_TO_SALE.value
            self.save()

            trigger_event(LoanOrderEvents.CONVERTED, id=self.pk)

    def _action_write_off(self, *args, **kwargs):
        """Mark the LoanOrder as WRITTEN_OFF."""
        if self.can_write_off:
            self.status = LoanOrderStatus.WRITTEN_OFF.value
            self.save()

            trigger_event(LoanOrderEvents.WRITTEN_OFF, id=self.pk)

    @transaction.atomic
    def approve_order(self):
        """Approve this loan order (requires superuser permission)."""
        if self.line_count == 0:
            raise ValidationError(_('Cannot approve a loan order with no line items'))
        if not self._validate_transition(LoanOrderStatus.APPROVED.value):
            raise ValidationError(_('Cannot approve order from current status'))
        return self.handle_transition(
            self.status, LoanOrderStatus.APPROVED.value, self, self._action_approve
        )

    @transaction.atomic
    def issue_order(self):
        """Issue this loan order."""
        if self.line_count == 0:
            raise ValidationError(_('Cannot issue a loan order with no line items'))
        if not self._validate_transition(LoanOrderStatus.ISSUED.value):
            raise ValidationError(_('Cannot issue order from current status'))
        return self.handle_transition(
            self.status, LoanOrderStatus.ISSUED.value, self, self._action_issue
        )

    @transaction.atomic
    def hold_order(self):
        """Place this loan order on hold."""
        if not self._validate_transition(LoanOrderStatus.ON_HOLD.value):
            raise ValidationError(_('Cannot hold order from current status'))
        return self.handle_transition(
            self.status, LoanOrderStatus.ON_HOLD.value, self, self._action_hold
        )

    @transaction.atomic
    def cancel_order(self):
        """Cancel this loan order."""
        if not self._validate_transition(LoanOrderStatus.CANCELLED.value):
            raise ValidationError(_('Cannot cancel order from current status'))
        return self.handle_transition(
            self.status, LoanOrderStatus.CANCELLED.value, self, self._action_cancel
        )

    @transaction.atomic
    def return_order(self):
        """Mark this loan order as returned."""
        if self.line_count == 0:
            raise ValidationError(_('Cannot return a loan order with no line items'))
        if not self._validate_transition(LoanOrderStatus.RETURNED.value):
            raise ValidationError(_('Cannot return order from current status'))
        return self.handle_transition(
            self.status, LoanOrderStatus.RETURNED.value, self, self._action_return
        )

    @transaction.atomic
    def convert_to_sale(self):
        """Convert this loan order to a sale."""
        if not self._validate_transition(LoanOrderStatus.CONVERTED_TO_SALE.value):
            raise ValidationError(_('Cannot convert order from current status'))
        return self.handle_transition(
            self.status, LoanOrderStatus.CONVERTED_TO_SALE.value, self, self._action_convert
        )

    @transaction.atomic
    def write_off_order(self):
        """Write off this loan order."""
        if not self._validate_transition(LoanOrderStatus.WRITTEN_OFF.value):
            raise ValidationError(_('Cannot write off order from current status'))
        return self.handle_transition(
            self.status, LoanOrderStatus.WRITTEN_OFF.value, self, self._action_write_off
        )

    # endregion

    # region Stock Operations

    @transaction.atomic
    def ship_line_items(self, items: list, user: User, **kwargs) -> QuerySet:
        """Ship items out on loan.

        Arguments:
            items: List of dicts with line_item, stock_item, quantity
            user: The user performing the action
        """
        if self.status not in [
            LoanOrderStatus.ISSUED.value,
            LoanOrderStatus.SHIPPED.value,
            LoanOrderStatus.PARTIAL_RETURN.value,
        ]:
            # Auto-issue if pending or approved
            if self.status in [
                LoanOrderStatus.PENDING.value,
                LoanOrderStatus.APPROVED.value,
            ]:
                self.issue_order()
            else:
                raise ValidationError(_('Cannot ship items for this loan status'))

        shipped_allocations = []

        for item in items:
            line_item = item['line_item']
            stock_item = item['stock_item']
            quantity = Decimal(str(item['quantity']))

            # Validate the allocation
            if line_item.order != self:
                raise ValidationError(_('Line item does not belong to this order'))

            if quantity <= 0:
                raise ValidationError(_('Quantity must be greater than zero'))

            # Check that we don't ship more than the line item requires
            remaining_to_ship = line_item.quantity - line_item.shipped
            if quantity > remaining_to_ship:
                raise ValidationError(
                    _('Shipping quantity ({qty}) exceeds remaining quantity ({remaining})').format(
                        qty=quantity, remaining=remaining_to_ship,
                    )
                )

            # Check unallocated quantity on stock item
            available = stock_item.unallocated_quantity()
            if quantity > available:
                raise ValidationError(
                    _('Requested quantity exceeds available stock ({available})').format(
                        available=available,
                    )
                )

            # Create or update allocation
            allocation, created = LoanOrderAllocation.objects.get_or_create(
                line=line_item,
                item=stock_item,
                defaults={'quantity': quantity},
            )

            if not created:
                allocation.quantity += quantity
                allocation.save()

            shipped_allocations.append(allocation)

            # Update line item status
            line_item.shipped += quantity
            if line_item.shipped >= line_item.quantity:
                line_item.status = LoanOrderLineStatus.SHIPPED.value
            line_item.save()

            # Add tracking entry for the stock item
            stock_item.add_tracking_entry(
                StockHistoryCode.LOANED_OUT,
                user,
                deltas={
                    'loanorder': self.pk,
                    'quantity': float(quantity),
                },
            )

        # Auto-transition order to SHIPPED when any line item is fully shipped
        if self.status == LoanOrderStatus.ISSUED.value:
            if self.lines.filter(
                status=LoanOrderLineStatus.SHIPPED.value
            ).exists():
                self.status = LoanOrderStatus.SHIPPED.value
                self.ship_date = self.ship_date or InvenTree.helpers.current_date()
                self.save()
                trigger_event(LoanOrderEvents.SHIPPED, id=self.pk)

        trigger_event(
            LoanOrderEvents.LINE_ITEM_SHIPPED,
            order_id=self.pk,
            allocation_ids=[a.pk for a in shipped_allocations],
        )

        return LoanOrderAllocation.objects.filter(
            pk__in=[a.pk for a in shipped_allocations]
        )

    @transaction.atomic
    def ship_all_line_items(self, user: User, **kwargs) -> QuerySet:
        """Auto-allocate stock and ship all pending line items.

        For each line item with unshipped quantity, finds the first available
        stock item with sufficient unallocated quantity and ships it.

        Arguments:
            user: The user performing the action

        Raises:
            ValidationError: If no pending items or insufficient stock
        """
        from stock.models import StockItem

        pending = self.lines.filter(shipped__lt=F('quantity'))
        if not pending.exists():
            raise ValidationError(_('No pending items to ship'))

        items_to_ship = []
        for line in pending:
            remaining = line.quantity - line.shipped
            # Find stock item with sufficient available quantity
            stock_items = StockItem.objects.filter(
                part=line.part,
                quantity__gt=0,
            ).order_by('-quantity')

            suitable = None
            for si in stock_items:
                if si.unallocated_quantity() >= remaining:
                    suitable = si
                    break

            if suitable is None:
                raise ValidationError(
                    _('No suitable stock for %(part)s (need %(qty)s)')
                    % {'part': line.part.name, 'qty': remaining}
                )

            items_to_ship.append({
                'line_item': line,
                'stock_item': suitable,
                'quantity': remaining,
            })

        return self.ship_line_items(items_to_ship, user, **kwargs)

    @transaction.atomic
    def return_line_items(self, items: list, user: User, location=None, **kwargs) -> list:
        """Return items from loan.

        Arguments:
            items: List of dicts with allocation, quantity, and optional status
            user: The user performing the action
            location: Default location to return items to
        """
        if not self.is_open:
            raise ValidationError(_('Cannot return items for a closed loan'))

        returned_items = []

        for item in items:
            allocation = item['allocation']
            quantity = Decimal(str(item['quantity']))
            item_status = item.get('status', StockStatus.OK.value)
            return_location = item.get('location', location)

            if allocation.line.order != self:
                raise ValidationError(_('Allocation does not belong to this order'))

            if quantity <= 0:
                raise ValidationError(_('Quantity must be greater than zero'))

            if quantity > allocation.quantity:
                raise ValidationError(_('Return quantity exceeds allocated quantity'))

            # Return stock to inventory
            stock_item = allocation.item

            # Add tracking entry
            stock_item.add_tracking_entry(
                StockHistoryCode.RETURNED_FROM_LOAN,
                user,
                deltas={
                    'loanorder': self.pk,
                    'quantity': float(quantity),
                    'location': return_location.pk if return_location else None,
                },
            )

            # Update stock item status and location if specified
            if return_location:
                stock_item.location = return_location
            stock_item.set_status(item_status)
            stock_item.save()

            returned_items.append(stock_item)

            # Update allocation (keep record for traceability)
            allocation.quantity -= quantity
            allocation.returned += quantity
            allocation.save()

            # Update line item
            line = allocation.line
            line.returned += quantity
            if line.returned >= line.quantity:
                line.status = LoanOrderLineStatus.RETURNED.value
            line.save()

        trigger_event(
            LoanOrderEvents.LINE_ITEM_RETURNED,
            order_id=self.pk,
            item_ids=[i.pk for i in returned_items],
        )

        # Check if all items have been returned
        if self.pending_line_count == 0 and self.is_open:
            # Auto-complete the loan
            auto_complete = get_global_setting('LOANORDER_AUTO_COMPLETE', backup_value=True)
            if auto_complete:
                self.return_order()
        elif self.completed_line_count > 0 and self.pending_line_count > 0:
            # Some items returned, some still out -> PARTIAL_RETURN
            if self.status in [
                LoanOrderStatus.ISSUED.value,
                LoanOrderStatus.SHIPPED.value,
            ]:
                self.status = LoanOrderStatus.PARTIAL_RETURN.value
                self.save()
                trigger_event(LoanOrderEvents.PARTIAL_RETURN, id=self.pk)

        return returned_items

    # endregion


class LoanOrderLineItem(InvenTree.models.InvenTreeMetadataModel):
    """Model for a single line item in a LoanOrder.

    Attributes:
        order: Link to the LoanOrder
        part: Link to a Part object
        quantity: Number of items to loan
        shipped: Number of items actually shipped
        returned: Number of items returned
        reference: Reference text
        notes: Notes for this line item
        target_date: Target date for this line item
        status: Status of this line item
    """

    class Meta:
        """Model meta options."""

        verbose_name = _('Loan Order Line Item')
        verbose_name_plural = _('Loan Order Line Items')

    def save(self, *args, **kwargs):
        """Custom save method."""
        if self.order and self.order.check_locked():
            raise ValidationError({
                'non_field_errors': _('The order is locked and cannot be modified')
            })

        update_order = kwargs.pop('update_order', True)
        super().save(*args, **kwargs)

        if update_order and self.order:
            self.order.save()

    def delete(self, *args, **kwargs):
        """Custom delete method."""
        if self.order and self.order.check_locked():
            raise ValidationError({
                'non_field_errors': _('The order is locked and cannot be modified')
            })

        super().delete(*args, **kwargs)
        self.order.save()

    def clean(self) -> None:
        """Validate the line item."""
        super().clean()

        errors = {}

        # Quantity must be positive
        if self.quantity is not None and self.quantity <= 0:
            errors['quantity'] = _('Quantity must be greater than zero')

        if self.part:
            if not self.part.salable:
                errors['part'] = _('Only salable parts can be added to a loan order')
            if not self.part.active:
                errors['part'] = _('Part is not active')

        # Consistency checks (only on update, not initial creation)
        if self.pk:
            if self.shipped > self.quantity:
                errors['shipped'] = _('Shipped quantity cannot exceed order quantity')
            if self.returned > self.shipped:
                errors['returned'] = _('Returned quantity cannot exceed shipped quantity')

        # Cannot add lines to completed/cancelled orders
        if self.order_id:
            order_status = self.order.status
            if order_status in (
                LoanOrderStatusGroups.COMPLETE + LoanOrderStatusGroups.FAILED
            ):
                errors['order'] = _('Cannot modify line items for a completed or cancelled order')

        # Line item target_date cannot exceed the order's due_date
        if self.target_date and self.order_id and self.order.due_date:
            if self.target_date > self.order.due_date:
                errors['target_date'] = _('Target date cannot be after the order due date')

        if errors:
            raise ValidationError(errors)

    @staticmethod
    def get_api_url():
        """Return the API URL for this model."""
        return reverse('api-loan-order-line-list')

    # Filter for overdue line items
    OVERDUE_FILTER = (
        Q(returned__lt=F('quantity'))
        & ~Q(target_date=None)
        & Q(target_date__lt=InvenTree.helpers.current_date())
    )

    order = models.ForeignKey(
        LoanOrder,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name=_('Order'),
        help_text=_('Loan Order'),
    )

    part = models.ForeignKey(
        'part.Part',
        on_delete=models.SET_NULL,
        related_name='loan_order_line_items',
        null=True,
        verbose_name=_('Part'),
        help_text=_('Part'),
        limit_choices_to={'salable': True},
    )

    quantity = RoundingDecimalField(
        verbose_name=_('Quantity'),
        help_text=_('Item quantity'),
        default=1,
        max_digits=15,
        decimal_places=5,
        validators=[MinValueValidator(0)],
    )

    shipped = RoundingDecimalField(
        verbose_name=_('Shipped'),
        help_text=_('Quantity shipped out on loan'),
        default=0,
        max_digits=15,
        decimal_places=5,
        validators=[MinValueValidator(0)],
    )

    returned = RoundingDecimalField(
        verbose_name=_('Returned'),
        help_text=_('Quantity returned from loan'),
        default=0,
        max_digits=15,
        decimal_places=5,
        validators=[MinValueValidator(0)],
    )

    status = InvenTreeCustomStatusModelField(
        default=LoanOrderLineStatus.PENDING.value,
        choices=LoanOrderLineStatus.items(),
        status_class=LoanOrderLineStatus,
        verbose_name=_('Status'),
        help_text=_('Line item status'),
    )

    loan_price = InvenTreeModelMoneyField(
        max_digits=19,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_('Loan Price'),
        help_text=_('Unit loan price (rental fee)'),
    )

    @property
    def price(self):
        """Return the 'loan_price' field as 'price'."""
        return self.loan_price

    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Reference'),
        help_text=_('Line item reference'),
    )

    notes = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Line item notes'),
    )

    link = InvenTreeURLField(
        blank=True,
        verbose_name=_('Link'),
        help_text=_('Link to external page'),
        max_length=2000,
    )

    target_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Target Date'),
        help_text=_('Target return date for this line item'),
    )

    project_code = models.ForeignKey(
        common_models.ProjectCode,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_('Project Code'),
        help_text=_('Select project code for this line item'),
    )

    # Conversion tracking fields
    converted_quantity = RoundingDecimalField(
        verbose_name=_('Converted Quantity'),
        help_text=_('Total quantity converted to sale'),
        default=0,
        max_digits=15,
        decimal_places=5,
        validators=[MinValueValidator(0)],
    )

    returned_and_sold_quantity = RoundingDecimalField(
        verbose_name=_('Returned and Sold Quantity'),
        help_text=_('Quantity that was returned from loan then sold separately'),
        default=0,
        max_digits=15,
        decimal_places=5,
        validators=[MinValueValidator(0)],
    )

    converted_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Conversion Date'),
        help_text=_('Date when items were first converted to sale'),
    )

    @property
    def total_line_price(self):
        """Return the total price for this line item."""
        if self.price:
            return self.quantity * self.price
        return None

    def allocated_quantity(self) -> Decimal:
        """Return total quantity allocated for this line item."""
        if not self.pk:
            return Decimal(0)

        query = self.allocations.aggregate(
            allocated=Coalesce(Sum('quantity'), Decimal(0))
        )
        return query['allocated']

    def on_loan_quantity(self) -> Decimal:
        """Return quantity currently out on loan (shipped but not returned)."""
        return self.shipped - self.returned

    def is_fully_allocated(self) -> bool:
        """Return True if this line item is fully allocated."""
        if self.part and self.part.virtual:
            return True
        return self.allocated_quantity() >= self.quantity

    def is_overallocated(self) -> bool:
        """Return True if this line item is over allocated."""
        return self.allocated_quantity() > self.quantity

    def is_completed(self) -> bool:
        """Return True if this line item is completed."""
        if self.part and self.part.virtual:
            return True
        return self.returned >= self.quantity

    # Conversion-related properties and methods

    @property
    def remaining_on_loan(self) -> Decimal:
        """Return quantity still on loan (not returned, not converted)."""
        return self.shipped - self.returned - self.converted_quantity

    @property
    def available_to_convert(self) -> Decimal:
        """Return quantity available to convert to sale (currently on loan)."""
        return self.remaining_on_loan

    @property
    def available_returned_to_sell(self) -> Decimal:
        """Return quantity of returned items available to sell."""
        return self.returned - self.returned_and_sold_quantity

    @property
    def is_fully_converted(self) -> bool:
        """Check if all loaned items have been converted to sale."""
        return self.converted_quantity >= self.shipped

    @property
    def is_partially_converted(self) -> bool:
        """Check if some (but not all) loaned items have been converted."""
        return Decimal(0) < self.converted_quantity < self.shipped

    def can_convert_to_sale(self, quantity: Decimal = None) -> bool:
        """Check if line item can be converted to sale.

        Args:
            quantity: Optional quantity to check. If not provided, checks if any conversion is possible.

        Returns:
            bool: True if conversion is possible
        """
        # Check if there are items on loan
        if self.remaining_on_loan <= 0:
            return False

        # Check specific quantity if provided
        if quantity is not None:
            if quantity <= 0:
                return False
            if quantity > self.remaining_on_loan:
                return False

        # Check order status allows conversion
        if self.order.status not in [
            LoanOrderStatus.ISSUED.value,
            LoanOrderStatus.SHIPPED.value,
            LoanOrderStatus.PARTIAL_RETURN.value,
        ]:
            return False

        return True

    def can_sell_returned_items(self, quantity: Decimal = None) -> bool:
        """Check if returned items can be sold.

        Args:
            quantity: Optional quantity to check.

        Returns:
            bool: True if selling returned items is possible
        """
        # Check if there are returned items available
        if self.available_returned_to_sell <= 0:
            return False

        # Check specific quantity if provided
        if quantity is not None:
            if quantity <= 0:
                return False
            if quantity > self.available_returned_to_sell:
                return False

        return True

    def _create_or_update_sales_order(
        self,
        quantity: Decimal,
        sale_price,
        existing_sales_order=None,
        is_returned_items=False,
        user=None,
        notes='',
    ):
        """Create or update sales order with line item.

        This is a helper method that handles the actual creation of SalesOrder
        and SalesOrderLineItem objects for conversions.

        Args:
            quantity: Quantity to add to sales order
            sale_price: Sale price per unit (Money object)
            existing_sales_order: Optional existing SO to add to
            is_returned_items: Whether these are returned items or on-loan items
            user: User performing the conversion
            notes: Additional notes

        Returns:
            tuple: (SalesOrder, SalesOrderLineItem) created/updated

        Raises:
            ValidationError: If SO creation fails
        """
        from order import models as order_models

        # Get or create Sales Order
        if existing_sales_order:
            sales_order = existing_sales_order
        else:
            # Generate unique reference for Sales Order
            base_ref = f'SO-LOAN-{self.order.pk}'
            reference = base_ref
            suffix = 1

            # Ensure reference is unique
            while order_models.SalesOrder.objects.filter(reference=reference).exists():
                reference = f'{base_ref}-{suffix}'
                suffix += 1

            # Create new sales order
            sales_order = order_models.SalesOrder.objects.create(
                customer=self.order.borrower_company,
                description=_('Conversion from loan order {ref}').format(
                    ref=self.order.reference
                ),
                reference=reference,
                created_by=user,
            )

            # Link back to loan order
            self.order.converted_sales_order = sales_order
            self.order.save()

        # Create sales order line item
        sales_line = order_models.SalesOrderLineItem.objects.create(
            order=sales_order,
            part=self.part,
            quantity=quantity,
            sale_price=sale_price.amount if sale_price else 0,
            sale_price_currency=sale_price.currency if sale_price else 'USD',
            notes=_(
                'Converted from loan {ref} line {line_pk}\n'
                'Type: {item_type}\n'
                '{notes}'
            ).format(
                ref=self.order.reference,
                line_pk=self.pk,
                item_type=_('Returned items') if is_returned_items else _('Items on loan'),
                notes=notes,
            ),
        )

        # Handle stock allocations
        if is_returned_items:
            # For returned items, we need to allocate from the stock location
            # where items were returned
            # The stock items should already be back in inventory
            pass  # Stock allocation will be handled by sales order fulfillment

        else:
            # For items still on loan, transfer allocations
            # Find loan allocations for this line item
            loan_allocations = self.allocations.filter(
                quantity__gt=models.F('returned')
            ).select_related('item')

            # Calculate how much we need to allocate
            remaining_to_allocate = quantity

            for loan_alloc in loan_allocations:
                if remaining_to_allocate <= 0:
                    break

                # Calculate available quantity from this allocation
                available = loan_alloc.quantity - loan_alloc.returned
                alloc_quantity = min(available, remaining_to_allocate)

                if alloc_quantity > 0:
                    # Create sales order allocation from same stock item
                    so_alloc = order_models.SalesOrderAllocation.objects.create(
                        line=sales_line,
                        item=loan_alloc.item,
                        quantity=alloc_quantity,
                    )

                    # Mark loan allocation as converted
                    loan_alloc.is_converted = True
                    loan_alloc.converted_to_sales_allocation = so_alloc
                    loan_alloc.save()

                    remaining_to_allocate -= alloc_quantity

        return sales_order, sales_line

    @transaction.atomic
    def convert_to_sales_order(
        self,
        quantity: Decimal,
        user=None,
        sale_price=None,
        existing_sales_order=None,
        notes='',
    ):
        """Convert loaned items to a sales order.

        This method converts items that are currently on loan to a sales order.
        It creates a LoanOrderLineConversion record and optionally creates or updates a sales order.

        Args:
            quantity: Quantity to convert
            user: User performing the conversion
            sale_price: Price per unit for the sale (Money object)
            existing_sales_order: Optional existing SalesOrder to add to
            notes: Additional notes for the conversion

        Returns:
            LoanOrderLineConversion: The conversion record created

        Raises:
            ValidationError: If conversion is not allowed or quantity is invalid
        """
        from decimal import Decimal as D

        # Validate conversion
        if not self.can_convert_to_sale(quantity):
            raise ValidationError(_('Cannot convert this quantity to sale'))

        # Create or update sales order
        sales_order, sales_line = self._create_or_update_sales_order(
            quantity=D(str(quantity)),
            sale_price=sale_price,
            existing_sales_order=existing_sales_order,
            is_returned_items=False,
            user=user,
            notes=notes,
        )

        # Create conversion record
        conversion = LoanOrderLineConversion(
            loan_line=self,
            sales_order_line=sales_line,
            quantity=D(str(quantity)),
            converted_by=user,
            is_returned_items=False,
            conversion_price=sale_price,
            notes=notes,
        )

        conversion.full_clean()
        conversion.save()

        # Update line item converted_quantity
        self.converted_quantity += D(str(quantity))
        if not self.converted_date:
            self.converted_date = conversion.converted_date
        self.save(update_order=False)

        # Update line item status
        if self.is_fully_converted:
            self.status = LoanOrderLineStatus.CONVERTED_TO_SALE.value
        elif self.is_partially_converted:
            self.status = LoanOrderLineStatus.PARTIALLY_CONVERTED.value
        self.save()

        return conversion

    @transaction.atomic
    def sell_returned_items(
        self,
        quantity: Decimal,
        user=None,
        sale_price=None,
        existing_sales_order=None,
        notes='',
    ):
        """Sell items that have been returned from loan.

        This is separate from convert_to_sales_order because these items
        have already been returned to stock.

        Args:
            quantity: Quantity of returned items to sell
            user: User performing the sale
            sale_price: Price per unit for the sale
            existing_sales_order: Optional existing SalesOrder to add to
            notes: Additional notes

        Returns:
            LoanOrderLineConversion: The conversion record created

        Raises:
            ValidationError: If sale is not allowed or quantity is invalid
        """
        from decimal import Decimal as D

        # Validate
        if not self.can_sell_returned_items(quantity):
            raise ValidationError(_('Cannot sell this quantity of returned items'))

        # Create or update sales order for returned items
        sales_order, sales_line = self._create_or_update_sales_order(
            quantity=D(str(quantity)),
            sale_price=sale_price,
            existing_sales_order=existing_sales_order,
            is_returned_items=True,
            user=user,
            notes=notes,
        )

        # Create conversion record for returned items
        conversion = LoanOrderLineConversion(
            loan_line=self,
            sales_order_line=sales_line,
            quantity=D(str(quantity)),
            converted_by=user,
            is_returned_items=True,
            conversion_price=sale_price,
            notes=notes,
        )

        conversion.full_clean()
        conversion.save()

        # Update returned_and_sold_quantity
        self.returned_and_sold_quantity += D(str(quantity))
        self.save()

        return conversion


class LoanOrderAllocation(models.Model):
    """Model to allocate stock items to a LoanOrder.

    Attributes:
        line: LoanOrderLineItem reference
        item: StockItem reference
        quantity: Quantity allocated (still out on loan)
        returned: Quantity that has been returned
    """

    class Meta:
        """Model meta options."""

        verbose_name = _('Loan Order Allocation')
        verbose_name_plural = _('Loan Order Allocations')

    @staticmethod
    def get_api_url():
        """Return the API URL for this model."""
        return reverse('api-loan-order-allocation-list')

    def clean(self):
        """Validate the allocation."""
        super().clean()

        errors = {}

        try:
            if not self.item:
                raise ValidationError({'item': _('Stock item has not been assigned')})
        except stock.models.StockItem.DoesNotExist:
            raise ValidationError({'item': _('Stock item has not been assigned')})

        # Part must match
        try:
            if self.line.part != self.item.part:
                variants = self.line.part.get_descendants(include_self=True)
                if self.line.part not in variants:
                    errors['item'] = _(
                        'Cannot allocate stock item to a line with a different part'
                    )
        except PartModels.Part.DoesNotExist:
            errors['line'] = _('Cannot allocate stock to a line without a part')

        if self.quantity > self.item.quantity:
            errors['quantity'] = _('Allocation quantity cannot exceed stock quantity')

        # Check for over-allocation (including loans!)
        build_allocation = self.item.build_allocation_count()
        sales_allocation = self.item.sales_order_allocation_count(
            exclude_allocations={'pk': self.pk if self.pk else None}
        )
        # Get loan allocations excluding this one
        loan_allocation = self.item.loan_allocation_count(
            exclude_allocations={'pk': self.pk if self.pk else None}
        )

        total_allocation = (
            build_allocation + sales_allocation + loan_allocation + self.quantity
        )

        if total_allocation > self.item.quantity:
            errors['quantity'] = _('Stock item is over-allocated')

        if self.quantity <= 0:
            errors['quantity'] = _('Allocation quantity must be greater than zero')

        if self.item.serial and self.quantity != 1:
            errors['quantity'] = _('Quantity must be 1 for serialized stock item')

        if len(errors) > 0:
            raise ValidationError(errors)

    line = models.ForeignKey(
        LoanOrderLineItem,
        on_delete=models.CASCADE,
        verbose_name=_('Line'),
        related_name='allocations',
    )

    item = models.ForeignKey(
        'stock.StockItem',
        on_delete=models.CASCADE,
        related_name='loan_order_allocations',
        limit_choices_to={
            'part__salable': True,
            'part__virtual': False,
            'belongs_to': None,
            'sales_order': None,
        },
        verbose_name=_('Item'),
        help_text=_('Select stock item to allocate'),
    )

    quantity = RoundingDecimalField(
        max_digits=15,
        decimal_places=5,
        validators=[MinValueValidator(0)],
        default=1,
        verbose_name=_('Quantity'),
        help_text=_('Enter stock allocation quantity'),
    )

    returned = RoundingDecimalField(
        max_digits=15,
        decimal_places=5,
        validators=[MinValueValidator(0)],
        default=0,
        verbose_name=_('Returned'),
        help_text=_('Quantity returned from this allocation'),
    )

    # Conversion tracking fields
    is_converted = models.BooleanField(
        default=False,
        verbose_name=_('Is Converted'),
        help_text=_('Whether this allocation has been converted to sale'),
    )

    converted_to_sales_allocation = models.ForeignKey(
        'order.SalesOrderAllocation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='converted_from_loan_allocation',
        verbose_name=_('Converted to Sales Allocation'),
        help_text=_('Sales Order allocation this was converted to'),
    )

    def get_location(self):
        """Return the location pk of the allocated stock item."""
        return self.item.location.pk if self.item.location else None


class LoanOrderExtraLine(InvenTree.models.InvenTreeMetadataModel):
    """Model for extra line items in a LoanOrder (fees, deposits, etc.).

    Attributes:
        order: Link to the LoanOrder
        quantity: Quantity (typically 1)
        reference: Reference text
        notes: Notes
        price: Unit price
        description: Description of the extra charge
    """

    class Meta:
        """Model meta options."""

        verbose_name = _('Loan Order Extra Line')
        verbose_name_plural = _('Loan Order Extra Lines')

    @staticmethod
    def get_api_url() -> str:
        """Return the API URL for this model."""
        return reverse('api-loan-order-extra-line-list')

    def save(self, *args, **kwargs):
        """Custom save method."""
        if self.order and self.order.check_locked():
            raise ValidationError({
                'non_field_errors': _('The order is locked and cannot be modified')
            })

        update_order = kwargs.pop('update_order', True)
        super().save(*args, **kwargs)

        if update_order and self.order:
            self.order.save()

    def delete(self, *args, **kwargs):
        """Custom delete method."""
        if self.order and self.order.check_locked():
            raise ValidationError({
                'non_field_errors': _('The order is locked and cannot be modified')
            })

        super().delete(*args, **kwargs)
        self.order.save()

    order = models.ForeignKey(
        LoanOrder,
        on_delete=models.CASCADE,
        related_name='extra_lines',
        verbose_name=_('Order'),
        help_text=_('Loan Order'),
    )

    quantity = RoundingDecimalField(
        verbose_name=_('Quantity'),
        help_text=_('Quantity'),
        default=1,
        max_digits=15,
        decimal_places=5,
        validators=[MinValueValidator(0)],
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Reference'),
        help_text=_('Line item reference'),
    )

    description = models.CharField(
        max_length=250,
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Description of the extra charge'),
    )

    notes = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Line item notes'),
    )

    price = InvenTreeModelMoneyField(
        max_digits=19,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_('Price'),
        help_text=_('Unit price'),
    )

    link = InvenTreeURLField(
        blank=True,
        verbose_name=_('Link'),
        help_text=_('Link to external page'),
        max_length=2000,
    )

    @property
    def total_line_price(self):
        """Return the total price for this line item."""
        if self.price:
            return self.quantity * self.price
        return None


class LoanOrderLineConversion(models.Model):
    """Model to track conversions from loan line items to sales orders.

    This model supports multiple partial conversions from the same loan line item,
    allowing granular tracking of which quantities were converted and when.

    Attributes:
        loan_line: The loan order line item being converted
        sales_order_line: The sales order line item created from conversion
        quantity: Quantity converted in this conversion
        converted_date: When the conversion occurred
        converted_by: User who performed the conversion
        is_returned_items: Whether these items were returned before conversion
        conversion_price: Price at which items were sold (may differ from loan price)
        notes: Additional notes about the conversion
    """

    class Meta:
        """Model meta options."""

        verbose_name = _('Loan Order Line Conversion')
        verbose_name_plural = _('Loan Order Line Conversions')
        ordering = ['-converted_date']

    @staticmethod
    def get_api_url():
        """Return the API URL for this model."""
        return reverse('api-loan-order-line-conversion-list')

    loan_line = models.ForeignKey(
        LoanOrderLineItem,
        on_delete=models.CASCADE,
        related_name='conversions',
        verbose_name=_('Loan Line Item'),
        help_text=_('Loan order line item being converted'),
    )

    sales_order_line = models.ForeignKey(
        'order.SalesOrderLineItem',
        on_delete=models.PROTECT,
        related_name='converted_from_loan',
        null=True,
        blank=True,
        verbose_name=_('Sales Order Line'),
        help_text=_('Sales order line item created from this conversion'),
    )

    quantity = RoundingDecimalField(
        max_digits=15,
        decimal_places=5,
        validators=[MinValueValidator(0)],
        verbose_name=_('Quantity'),
        help_text=_('Quantity converted in this conversion'),
    )

    converted_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Conversion Date'),
        help_text=_('Date and time when conversion occurred'),
    )

    converted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Converted By'),
        help_text=_('User who performed the conversion'),
    )

    is_returned_items = models.BooleanField(
        default=False,
        verbose_name=_('Is Returned Items'),
        help_text=_('Whether these items were returned from loan before conversion'),
    )

    conversion_price = InvenTreeModelMoneyField(
        max_digits=19,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_('Conversion Price'),
        help_text=_('Unit price at which items were sold'),
    )

    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Additional notes about this conversion'),
    )

    def clean(self):
        """Validate the conversion."""
        super().clean()

        errors = {}

        # Validate quantity doesn't exceed available
        if self.loan_line:
            if self.is_returned_items:
                # Converting returned items
                available = self.loan_line.returned - self.loan_line.returned_and_sold_quantity
                if self.quantity > available:
                    errors['quantity'] = _(
                        'Conversion quantity cannot exceed returned quantity not yet sold'
                    )
            else:
                # Converting items still on loan
                available = self.loan_line.shipped - self.loan_line.returned - self.loan_line.converted_quantity
                if self.quantity > available:
                    errors['quantity'] = _(
                        'Conversion quantity cannot exceed quantity still on loan'
                    )

        if len(errors) > 0:
            raise ValidationError(errors)

    def __str__(self):
        """String representation."""
        return f'Conversion of {self.quantity} from {self.loan_line.order.reference} to SO'
