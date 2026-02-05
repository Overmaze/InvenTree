# Loans Module - Implementation Proposal

## Executive Summary

This document provides a comprehensive proposal for implementing the Loans module in InvenTree, based on the planning document `LOANS_MODULE_PLANNING.md`. All code, comments, and documentation will be in English.

**Status**: Proposal - Awaiting Approval
**Module Name**: `loan` (backend), `loans` (frontend)
**Implementation**: Not Started - Requires Approval

---

## Table of Contents

1. [File Structure](#file-structure)
2. [Backend Files to Create](#backend-files-to-create)
3. [Frontend Files to Create](#frontend-files-to-create)
4. [Files to Modify](#files-to-modify)
5. [Testing Information](#testing-information)

---

## File Structure

### Backend Structure

```
src/backend/InvenTree/loan/
├── __init__.py
├── apps.py
├── models.py
├── serializers.py
├── api.py
├── admin.py
├── filters.py
├── status_codes.py
├── events.py
├── tasks.py
├── validators.py
├── migrations/
│   └── 0001_initial.py
├── fixtures/
│   └── loan.yaml
└── test_api.py
```

### Frontend Structure

```
src/frontend/src/
├── pages/loans/
│   ├── LoansIndex.tsx
│   └── LoanOrderDetail.tsx
├── tables/loans/
│   ├── LoanOrderTable.tsx
│   ├── LoanOrderLineItemTable.tsx
│   ├── LoanOrderAllocationTable.tsx
│   └── LoanOrderTrackingTable.tsx
└── forms/
    └── LoanForms.tsx
```

---

## Backend Files to Create

### 1. `src/backend/InvenTree/loan/__init__.py`

```python
"""Loan app for InvenTree."""

default_app_config = 'loan.apps.LoanConfig'
```

### 2. `src/backend/InvenTree/loan/apps.py`

```python
"""Config for the 'loan' app."""

from django.apps import AppConfig


class LoanConfig(AppConfig):
    """Configuration class for the 'loan' app."""

    name = 'loan'
```

### 3. `src/backend/InvenTree/loan/status_codes.py`

```python
"""Status codes for the loan app."""

from enum import IntEnum

from django.utils.translation import gettext_lazy as _

from generic.states import ColorEnum, StatusCode


class LoanOrderStatus(StatusCode):
    """Status codes for LoanOrder.

    NOTE: OVERDUE is NOT a status - it's a computed property based on due_date.
    Use the is_overdue property on the model to check overdue status.
    """

    PENDING = 10, _('Pending'), ColorEnum.info
    APPROVED = 20, _('Approved'), ColorEnum.success
    ISSUED = 30, _('Issued'), ColorEnum.success
    PARTIAL_RETURN = 40, _('Partially Returned'), ColorEnum.warning
    COMPLETE = 50, _('Complete'), ColorEnum.success
    CANCELLED = 60, _('Cancelled'), ColorEnum.danger


class LoanOrderStatusGroups:
    """Groups for LoanOrderStatus codes."""

    OPEN = [
        LoanOrderStatus.PENDING.value,
        LoanOrderStatus.APPROVED.value,
        LoanOrderStatus.ISSUED.value,
        LoanOrderStatus.PARTIAL_RETURN.value,
    ]

    COMPLETE = [LoanOrderStatus.COMPLETE.value]

    CANCELLED = [LoanOrderStatus.CANCELLED.value]


class LoanOrderLineStatus(StatusCode):
    """Status codes for LoanOrderLineItem."""

    PENDING = 10, _('Pending'), ColorEnum.info
    ALLOCATED = 20, _('Allocated'), ColorEnum.warning
    LOANED = 30, _('Loaned'), ColorEnum.success
    RETURNED = 40, _('Returned'), ColorEnum.success
    PARTIALLY_CONVERTED = 45, _('Partially Converted'), ColorEnum.warning
    CONVERTED_TO_SALE = 50, _('Converted to Sale'), ColorEnum.warning
    CANCELLED = 60, _('Cancelled'), ColorEnum.danger


class LoanOrderLineStatusGroups:
    """Groups for LoanOrderLineStatus codes."""

    PENDING = [LoanOrderLineStatus.PENDING.value]

    ACTIVE = [
        LoanOrderLineStatus.ALLOCATED.value,
        LoanOrderLineStatus.LOANED.value,
    ]

    CONVERTED = [
        LoanOrderLineStatus.CONVERTED_TO_SALE.value,
        LoanOrderLineStatus.PARTIALLY_CONVERTED.value,
    ]

    COMPLETE = [LoanOrderLineStatus.RETURNED.value]


class LoanTrackingCode(IntEnum):
    """Tracking codes for loan order history."""

    CREATED = 10
    APPROVED = 20
    ISSUED = 30
    ITEM_LOANED = 40
    ITEM_RETURNED = 50
    ITEM_CONVERTED_TO_SALE = 60
    COMPLETE = 70
    CANCELLED = 80
    OVERDUE_NOTIFIED = 90
    STATUS_CHANGE = 100
    RETURNED_ITEMS_SOLD = 110
```

### 4. `src/backend/InvenTree/loan/validators.py`

```python
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
```

### 5. `src/backend/InvenTree/loan/events.py`

```python
"""Event definitions for the loan app."""

from plugin.events import BaseEventEnum


class LoanOrderEvents(BaseEventEnum):
    """Event enumeration for LoanOrder models."""

    CREATED = 'loanorder.created'
    APPROVED = 'loanorder.approved'
    ISSUED = 'loanorder.issued'
    OVERDUE = 'loanorder.overdue'
    RETURNED = 'loanorder.returned'
    COMPLETED = 'loanorder.completed'
    CANCELLED = 'loanorder.cancelled'
```

### 6. `src/backend/InvenTree/loan/models.py`

```python
"""Models for the loan app."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q, Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

import InvenTree.models
import report.mixins
import loan.validators
from generic.states import StateTransitionMixin
from InvenTree.fields import InvenTreeCustomStatusModelField, RoundingDecimalField

from loan.status_codes import (
    LoanOrderStatus,
    LoanOrderStatusGroups,
    LoanOrderLineStatus,
    LoanOrderLineStatusGroups,
    LoanTrackingCode,
)
from stock.status_codes import StockHistoryCode


class LoanOrder(
    InvenTree.models.StatusCodeMixin,
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
    """Model representing a loan order.

    A loan order tracks the borrowing of stock items from inventory.
    """

    STATUS_CLASS = LoanOrderStatus

    # State machine: allowed transitions
    ALLOWED_TRANSITIONS = {
        LoanOrderStatus.PENDING.value: [
            LoanOrderStatus.APPROVED.value,
            LoanOrderStatus.CANCELLED.value,
        ],
        LoanOrderStatus.APPROVED.value: [
            LoanOrderStatus.ISSUED.value,
            LoanOrderStatus.CANCELLED.value,
        ],
        LoanOrderStatus.ISSUED.value: [
            LoanOrderStatus.PARTIAL_RETURN.value,
            LoanOrderStatus.COMPLETE.value,
            LoanOrderStatus.CANCELLED.value,
        ],
        LoanOrderStatus.PARTIAL_RETURN.value: [
            LoanOrderStatus.COMPLETE.value,
            LoanOrderStatus.CANCELLED.value,
        ],
        LoanOrderStatus.COMPLETE.value: [],  # Terminal state
        LoanOrderStatus.CANCELLED.value: [],  # Terminal state
    }

    # Reference pattern setting (required for ReferenceIndexingMixin)
    REFERENCE_PATTERN_SETTING = 'LOAN_ORDER_REFERENCE_PATTERN'

    # Reference number (auto-generated)
    reference = models.CharField(
        max_length=64,
        unique=True,
        help_text=_('Loan order reference'),
        verbose_name=_('Reference'),
        default=loan.validators.generate_next_loan_order_reference,
        validators=[loan.validators.validate_loan_order_reference],
    )

    @classmethod
    def validate_reference_field(cls, reference):
        """Validate the reference field matches the required pattern."""
        pattern = cls.get_reference_pattern()

        if not pattern:
            return

        # Validate pattern (implementation similar to Order.validate_reference_field)
        pass

    # Borrower - Owner (User or Group, NOT Company)
    # IMPORTANT: Owner can only point to User or Group, never Company directly
    borrower = models.ForeignKey(
        'users.Owner',
        on_delete=models.PROTECT,
        related_name='loan_orders',
        help_text=_('Borrower (user or group via Owner)'),
        verbose_name=_('Borrower'),
    )

    # Borrower Company - Direct reference to Company for customer tracking
    # This field allows linking loans to actual Company entities for reporting
    borrower_company = models.ForeignKey(
        'company.Company',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='loan_orders_as_borrower',
        help_text=_('Company borrowing the items'),
        verbose_name=_('Borrower Company'),
        limit_choices_to={'is_customer': True},
    )

    # Contact person
    contact = models.ForeignKey(
        'company.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loan_orders',
        help_text=_('Contact person for this loan'),
        verbose_name=_('Contact'),
    )

    # Shipping address (optional)
    address = models.ForeignKey(
        'company.Address',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loan_orders',
        help_text=_('Shipping address for loaned items'),
        verbose_name=_('Address'),
    )

    # Status tracking
    status = InvenTreeCustomStatusModelField(
        default=LoanOrderStatus.PENDING.value,
        verbose_name=_('Status'),
    )

    # Dates
    creation_date = models.DateField(
        auto_now_add=True,
        verbose_name=_('Creation Date'),
    )
    requested_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Requested Date'),
        help_text=_('Date when items are needed'),
    )
    issue_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Issue Date'),
        help_text=_('Date when items were loaned'),
    )
    due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Due Date'),
        help_text=_('Date when items should be returned'),
    )
    return_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Return Date'),
        help_text=_('Date when items were returned'),
    )

    # User tracking
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_loans',
        verbose_name=_('Created By'),
    )
    responsible = models.ForeignKey(
        'users.Owner',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responsible_loans',
        verbose_name=_('Responsible'),
        help_text=_('User or group responsible for this loan'),
    )
    issued_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_loans',
        verbose_name=_('Issued By'),
    )
    received_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_loans',
        verbose_name=_('Received By'),
    )

    # Project code (optional)
    project_code = models.ForeignKey(
        'common.ProjectCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loan_orders',
        verbose_name=_('Project Code'),
    )

    # Description
    description = models.CharField(
        max_length=500,
        help_text=_('Loan description'),
        verbose_name=_('Description'),
    )

    # Notes
    notes = models.TextField(
        blank=True,
        help_text=_('Additional notes'),
        verbose_name=_('Notes'),
    )

    class Meta:
        verbose_name = _('Loan Order')
        verbose_name_plural = _('Loan Orders')
        ordering = ['-creation_date']

    def __str__(self):
        return self.reference

    def get_absolute_url(self):
        """Return the absolute URL for this loan order."""
        return reverse('loan-detail', kwargs={'pk': self.pk})

    def get_api_url(self):
        """Return the API URL for this loan order."""
        return reverse('api-loan-order-detail', kwargs={'pk': self.pk})

    @property
    def is_overdue(self) -> bool:
        """Check if this loan is overdue.

        OVERDUE is a computed property, NOT a status value.
        A loan is overdue if:
        - It has a due_date set
        - The due_date is in the past
        - The loan is still in an OPEN status (not completed or cancelled)
        """
        if not self.due_date:
            return False
        if self.status not in LoanOrderStatusGroups.OPEN:
            return False
        return timezone.now().date() > self.due_date

    @staticmethod
    def overdue_filter():
        """Return Q filter for overdue loans."""
        today = timezone.now().date()
        return Q(
            due_date__lt=today,
            status__in=LoanOrderStatusGroups.OPEN
        )

    def can_transition_to(self, new_status: int) -> bool:
        """Check if transition to new_status is allowed."""
        current_status = self.status
        allowed = self.ALLOWED_TRANSITIONS.get(current_status, [])
        return new_status in allowed

    def handle_transition(self, new_status: int, user=None):
        """Handle status transition with validation.

        Args:
            new_status: The target status value
            user: User performing the transition

        Raises:
            ValidationError: If transition is not allowed
        """
        if not self.can_transition_to(new_status):
            current_name = LoanOrderStatus(self.status).name
            target_name = LoanOrderStatus(new_status).name
            raise ValidationError(
                _('Cannot transition from {current} to {target}').format(
                    current=current_name,
                    target=target_name
                )
            )

        self.status = new_status
        self.save()

        # Create tracking entry
        LoanOrderTracking.objects.create(
            order=self,
            tracking_type=LoanTrackingCode.STATUS_CHANGE,
            user=user,
            notes=_('Status changed to {status}').format(
                status=LoanOrderStatus(new_status).label
            ),
        )

    def approve(self, user=None):
        """Approve the loan order."""
        self.handle_transition(LoanOrderStatus.APPROVED.value, user)

        LoanOrderTracking.objects.create(
            order=self,
            tracking_type=LoanTrackingCode.APPROVED,
            user=user,
            notes=_('Loan order approved'),
        )

    def issue_loan(self, user=None):
        """Issue the loan (assign stock items).

        Note: Stock items must be allocated via LoanOrderAllocation before calling this method.
        This method marks the loan as issued and updates line item statuses.
        """
        # Validate that all lines have allocations
        for line in self.lines.all():
            if line.allocations.count() == 0:
                raise ValidationError(
                    _('Line item {line} has no stock allocations').format(
                        line=line.reference or str(line.pk)
                    )
                )

        # Complete allocations for all lines
        for line in self.lines.all():
            for allocation in line.allocations.all():
                allocation.complete_allocation(user=user)

        self.issue_date = timezone.now().date()
        self.issued_by = user
        self.handle_transition(LoanOrderStatus.ISSUED.value, user)

        LoanOrderTracking.objects.create(
            order=self,
            tracking_type=LoanTrackingCode.ISSUED,
            user=user,
            notes=_('Loan order issued'),
        )

    def complete_loan(self, user=None):
        """Mark loan as complete (all items returned)."""
        # Check all lines are returned
        for line in self.lines.all():
            if not line.is_complete():
                raise ValidationError(_('Not all items have been returned'))

        self.return_date = timezone.now().date()
        self.received_by = user
        self.handle_transition(LoanOrderStatus.COMPLETE.value, user)

        LoanOrderTracking.objects.create(
            order=self,
            tracking_type=LoanTrackingCode.COMPLETE,
            user=user,
            notes=_('Loan order completed'),
        )

    def cancel(self, user=None):
        """Cancel the loan order."""
        self.handle_transition(LoanOrderStatus.CANCELLED.value, user)

        LoanOrderTracking.objects.create(
            order=self,
            tracking_type=LoanTrackingCode.CANCELLED,
            user=user,
            notes=_('Loan order cancelled'),
        )


class LoanOrderLineItem(InvenTree.models.InvenTreeModel):
    """Model representing a line item in a loan order.

    Links a Part to a loan order with quantity and status.
    Actual stock items are allocated via LoanOrderAllocation.
    """

    STATUS_CLASS = LoanOrderLineStatus

    # Link to loan order
    order = models.ForeignKey(
        'loan.LoanOrder',
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name=_('Loan Order'),
    )

    # Part being loaned (similar to SalesOrderLineItem)
    part = models.ForeignKey(
        'part.Part',
        on_delete=models.SET_NULL,
        null=True,
        related_name='loan_order_line_items',
        verbose_name=_('Part'),
        help_text=_('Part to loan'),
    )

    # Quantity
    quantity = RoundingDecimalField(
        max_digits=15,
        decimal_places=5,
        default=1,
        validators=[MinValueValidator(0)],
        verbose_name=_('Quantity'),
        help_text=_('Quantity to loan'),
    )

    # Quantity tracking
    loaned_quantity = RoundingDecimalField(
        max_digits=15,
        decimal_places=5,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Loaned Quantity'),
        help_text=_('Quantity actually loaned'),
    )

    returned_quantity = RoundingDecimalField(
        max_digits=15,
        decimal_places=5,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Returned Quantity'),
        help_text=_('Quantity returned'),
    )

    converted_quantity = RoundingDecimalField(
        max_digits=15,
        decimal_places=5,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Converted Quantity'),
        help_text=_('Total quantity converted to sale'),
    )

    converted_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Conversion Date'),
        help_text=_('Date when items were first converted to sale'),
    )

    returned_and_sold_quantity = RoundingDecimalField(
        max_digits=15,
        decimal_places=5,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Returned and Sold Quantity'),
        help_text=_('Quantity that was returned and then sold'),
    )

    # Status
    status = InvenTreeCustomStatusModelField(
        default=LoanOrderLineStatus.PENDING.value,
        verbose_name=_('Status'),
    )

    # Reference
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Reference'),
    )

    # Notes
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
    )

    # Target date for this line
    target_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Target Date'),
    )

    class Meta:
        verbose_name = _('Loan Order Line Item')
        verbose_name_plural = _('Loan Order Line Items')
        unique_together = [('order', 'part')]

    def __str__(self):
        return f"{self.order.reference} - {self.part}"

    def is_complete(self):
        """Check if this line item is complete."""
        return self.returned_quantity >= self.loaned_quantity

    @property
    def is_overdue(self) -> bool:
        """Check if this line item is overdue."""
        if not self.target_date:
            return self.order.is_overdue
        if self.status in LoanOrderLineStatusGroups.COMPLETE:
            return False
        return timezone.now().date() > self.target_date

    def get_remaining_loanable_quantity(self):
        """Return quantity still available for loan (not converted or returned)."""
        return self.loaned_quantity - self.returned_quantity - self.converted_quantity

    def is_fully_converted(self):
        """Check if all loaned items have been converted to sale."""
        return self.converted_quantity >= self.loaned_quantity

    def is_partially_converted(self):
        """Check if some items have been converted but not all."""
        return self.converted_quantity > 0 and self.converted_quantity < self.loaned_quantity

    def can_sell_returned_items(self):
        """Check if there are returned items that can be sold."""
        return self.returned_quantity > self.returned_and_sold_quantity

    def allocate_stock(self, stock_item, quantity=None, user=None):
        """Allocate a stock item for loan.

        Args:
            stock_item: StockItem to allocate
            quantity: Quantity to allocate (defaults to line quantity)
            user: User performing the allocation
        """
        if quantity is None:
            quantity = self.quantity

        # Validate part matches
        if stock_item.part != self.part:
            raise ValidationError(_('Stock item part does not match line item part'))

        # Check availability using unallocated_quantity
        available = stock_item.unallocated_quantity()

        if available < quantity:
            raise ValidationError(
                _('Insufficient stock available. Available: {available}, Requested: {requested}').format(
                    available=available,
                    requested=quantity
                )
            )

        # Create allocation
        allocation = LoanOrderAllocation.objects.create(
            line=self,
            item=stock_item,
            quantity=quantity,
        )

        # Update line status
        self.status = LoanOrderLineStatus.ALLOCATED.value
        self.save()

        # Create tracking entry
        LoanOrderTracking.objects.create(
            order=self.order,
            tracking_type=LoanTrackingCode.ITEM_LOANED,
            user=user,
            notes=_('Stock allocated: {item} (quantity: {qty})').format(
                item=stock_item,
                qty=quantity,
            ),
        )

        return allocation

    def return_stock(self, quantity, user=None, condition=None):
        """Return stock item from loan."""
        allocations = self.allocations.filter(is_converted=False)
        total_allocated = sum(a.quantity for a in allocations)

        if quantity > total_allocated - self.returned_quantity:
            raise ValidationError(_('Cannot return more than loaned'))

        # Process return through allocations
        remaining = quantity
        for allocation in allocations:
            if remaining <= 0:
                break

            return_qty = min(remaining, allocation.quantity)
            allocation.return_allocation(return_qty, user=user, condition=condition)
            remaining -= return_qty

        self.returned_quantity += quantity
        self.save()

        # Update stock item status if fully returned
        if self.is_complete():
            self.status = LoanOrderLineStatus.RETURNED.value
            self.save()

        # Check if all lines are complete
        if self.order.lines.exclude(status=LoanOrderLineStatus.RETURNED.value).count() == 0:
            self.order.complete_loan(user)
        elif self.returned_quantity > 0 and self.order.status == LoanOrderStatus.ISSUED.value:
            self.order.handle_transition(LoanOrderStatus.PARTIAL_RETURN.value, user)

    @transaction.atomic
    def convert_to_sales_order(self, quantity, user=None, sale_price=None, existing_sales_order=None):
        """Convert loaned items to a sales order.

        Can either create a NEW SalesOrder or add to an EXISTING one.

        Args:
            quantity: Quantity to convert
            user: User performing the conversion
            sale_price: Optional sale price per unit
            existing_sales_order: Optional existing SalesOrder to add line to

        Returns:
            SalesOrder: The sales order (new or existing)
        """
        from order.models import SalesOrder, SalesOrderLineItem, SalesOrderAllocation

        # Validations
        if quantity <= 0:
            raise ValidationError(_('Quantity must be greater than zero'))

        remaining = self.get_remaining_loanable_quantity()
        if quantity > remaining:
            raise ValidationError(
                _('Cannot convert more than remaining loanable quantity: {remaining}').format(
                    remaining=remaining
                )
            )

        if self.status == LoanOrderLineStatus.CANCELLED.value:
            raise ValidationError(_('Cannot convert cancelled items'))

        # Use existing SalesOrder or create new one
        if existing_sales_order:
            sales_order = existing_sales_order
        else:
            # Use borrower_company if available, otherwise create a Company
            customer = self.order.borrower_company or self._get_or_create_customer_from_borrower(user)

            sales_order = SalesOrder.objects.create(
                customer=customer,
                created_by=user,
                description=_('Converted from loan order {ref}').format(
                    ref=self.order.reference
                ),
                notes=_('Items converted from loan order {loan_ref}').format(
                    loan_ref=self.order.reference
                ),
            )

        # Create SalesOrderLineItem
        sales_line = SalesOrderLineItem.objects.create(
            order=sales_order,
            part=self.part,
            quantity=quantity,
            sale_price=sale_price or (self.part.get_default_price() if self.part else None),
            reference=f'From Loan {self.order.reference}',
            notes=_('Converted from loan order {loan_ref}, line item {line_ref}').format(
                loan_ref=self.order.reference,
                line_ref=self.reference or str(self.pk)
            ),
        )

        # Get allocations to convert
        allocations = self.allocations.filter(is_converted=False).order_by('quantity')

        # Convert allocations
        remaining_qty = quantity
        converted_allocations = []

        for allocation in allocations:
            if remaining_qty <= 0:
                break

            convert_qty = min(remaining_qty, allocation.quantity)

            # Create SalesOrderAllocation
            sales_allocation = SalesOrderAllocation.objects.create(
                line=sales_line,
                item=allocation.item,
                quantity=convert_qty,
            )

            # Mark LoanOrderAllocation as converted
            if convert_qty == allocation.quantity:
                allocation.is_converted = True
                allocation.converted_to_sales_allocation = sales_allocation
                allocation.save()
                converted_allocations.append(allocation)
            else:
                # Partial conversion - create new allocation for remainder
                LoanOrderAllocation.objects.create(
                    line=self,
                    item=allocation.item,
                    quantity=allocation.quantity - convert_qty,
                )
                allocation.quantity = convert_qty
                allocation.is_converted = True
                allocation.converted_to_sales_allocation = sales_allocation
                allocation.save()
                converted_allocations.append(allocation)

            remaining_qty -= convert_qty

        # Update LoanOrderLineItem
        self.converted_quantity += quantity
        if not self.converted_date:
            self.converted_date = timezone.now()

        # Update status of LINE (NOT the LoanOrder)
        if self.is_fully_converted():
            self.status = LoanOrderLineStatus.CONVERTED_TO_SALE.value
        elif self.is_partially_converted():
            self.status = LoanOrderLineStatus.PARTIALLY_CONVERTED.value

        self.save()

        # Create conversion record
        LoanOrderLineConversion.objects.create(
            loan_line=self,
            sales_order_line=sales_line,
            quantity=quantity,
            converted_by=user,
            is_returned_items=False,
        )

        # Create tracking entry
        LoanOrderTracking.objects.create(
            order=self.order,
            tracking_type=LoanTrackingCode.ITEM_CONVERTED_TO_SALE,
            user=user,
            notes=_('{qty} items converted to sales order {so_ref}').format(
                qty=quantity,
                so_ref=sales_order.reference
            ),
        )

        # Track in stock items
        for allocation in converted_allocations:
            allocation.item.add_tracking_entry(
                StockHistoryCode.CONVERTED_FROM_LOAN_TO_SALE,
                user,
                {
                    'loan_order': self.order.pk,
                    'sales_order': sales_order.pk,
                    'quantity': str(allocation.quantity),
                },
                notes=_('Converted from loan to sale'),
            )

        return sales_order

    def _get_or_create_customer_from_borrower(self, user):
        """Get or create Company customer from Owner borrower.

        NOTE: Owner can only point to User or Group, NOT Company.
        This method creates a Company from the Owner's information.

        Returns:
            Company: Company instance (always created)
        """
        from company.models import Company

        borrower = self.order.borrower

        # Owner can only be User or Group, never Company
        if borrower.owner_type.model == 'user':
            user_obj = borrower.owner
            company_name = f"{user_obj.get_full_name() or user_obj.username} (Loan Borrower)"
            company_email = user_obj.email or None
        elif borrower.owner_type.model == 'group':
            group_obj = borrower.owner
            company_name = f"{group_obj.name} (Loan Borrower)"
            company_email = None
        else:
            company_name = f"{borrower.name()} (Loan Borrower)"
            company_email = None

        company = Company.objects.create(
            name=company_name,
            description=_('Auto-created from loan order {ref}').format(
                ref=self.order.reference
            ),
            email=company_email,
            is_customer=True,
            is_supplier=False,
            is_manufacturer=False,
            active=True,
        )

        return company

    @transaction.atomic
    def sell_returned_items(self, quantity, user=None, sale_price=None, existing_sales_order=None):
        """Sell items that were previously returned from loan.

        Args:
            quantity: Quantity to sell
            user: User performing the sale
            sale_price: Optional sale price per unit
            existing_sales_order: Optional existing SalesOrder to add line to

        Returns:
            SalesOrder: The sales order
        """
        from order.models import SalesOrder, SalesOrderLineItem

        if quantity <= 0:
            raise ValidationError(_('Quantity must be greater than zero'))

        available_returned = self.returned_quantity - self.returned_and_sold_quantity
        if quantity > available_returned:
            raise ValidationError(
                _('Cannot sell more than available returned quantity: {available}').format(
                    available=available_returned
                )
            )

        # Use existing SalesOrder or create new one
        if existing_sales_order:
            sales_order = existing_sales_order
        else:
            customer = self.order.borrower_company or self._get_or_create_customer_from_borrower(user)

            sales_order = SalesOrder.objects.create(
                customer=customer,
                created_by=user,
                description=_('Sold returned items from loan order {ref}').format(
                    ref=self.order.reference
                ),
                notes=_('Items were previously loaned and returned, now being sold').format(
                    loan_ref=self.order.reference
                ),
            )

        # Create SalesOrderLineItem
        sales_line = SalesOrderLineItem.objects.create(
            order=sales_order,
            part=self.part,
            quantity=quantity,
            sale_price=sale_price or (self.part.get_default_price() if self.part else None),
            reference=f'Returned from Loan {self.order.reference}',
            notes=_('Items returned from loan order {loan_ref} and now being sold').format(
                loan_ref=self.order.reference
            ),
        )

        # Update counter
        self.returned_and_sold_quantity += quantity
        self.save()

        # Create conversion record
        LoanOrderLineConversion.objects.create(
            loan_line=self,
            sales_order_line=sales_line,
            quantity=quantity,
            converted_by=user,
            is_returned_items=True,
        )

        # Tracking
        LoanOrderTracking.objects.create(
            order=self.order,
            tracking_type=LoanTrackingCode.RETURNED_ITEMS_SOLD,
            user=user,
            notes=_('{qty} returned items sold via sales order {so_ref}').format(
                qty=quantity,
                so_ref=sales_order.reference
            ),
        )

        return sales_order


class LoanOrderAllocation(models.Model):
    """Model for allocating stock items to loan orders.

    Similar to SalesOrderAllocation, this tracks which stock items
    are allocated to which loan order line items.
    """

    class Meta:
        verbose_name = _('Loan Order Allocation')
        unique_together = [('line', 'item')]

    line = models.ForeignKey(
        'loan.LoanOrderLineItem',
        on_delete=models.CASCADE,
        related_name='allocations',
        verbose_name=_('Line'),
    )

    item = models.ForeignKey(
        'stock.StockItem',
        on_delete=models.CASCADE,
        related_name='loan_allocations',
        verbose_name=_('Item'),
        help_text=_('Stock item allocated to loan'),
    )

    quantity = RoundingDecimalField(
        max_digits=15,
        decimal_places=5,
        validators=[MinValueValidator(0)],
        default=1,
        verbose_name=_('Quantity'),
        help_text=_('Quantity allocated'),
    )

    # Field to track conversion
    converted_to_sales_allocation = models.ForeignKey(
        'order.SalesOrderAllocation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='converted_from_loan_allocation',
        verbose_name=_('Converted to Sales Allocation'),
    )

    is_converted = models.BooleanField(
        default=False,
        verbose_name=_('Is Converted'),
        help_text=_('Whether this allocation has been converted to sale'),
    )

    def clean(self):
        """Validate the allocation."""
        super().clean()

        errors = {}

        # Check part matches
        if self.line.part != self.item.part:
            errors['item'] = _('Part mismatch')

        # Check quantity against UNALLOCATED quantity (not raw quantity)
        # This properly accounts for builds, sales orders, and other loans
        available = self.item.unallocated_quantity()

        # If editing existing allocation, add back our current quantity
        if self.pk:
            existing = LoanOrderAllocation.objects.get(pk=self.pk)
            available += existing.quantity

        if self.quantity > available:
            errors['quantity'] = _(
                'Allocation quantity ({requested}) exceeds available unallocated stock ({available})'
            ).format(requested=self.quantity, available=available)

        if errors:
            raise ValidationError(errors)

    def complete_allocation(self, user=None):
        """Complete the allocation (mark as loaned out)."""
        self.item.add_tracking_entry(
            StockHistoryCode.LOANED_OUT,
            user,
            {
                'loan_order': self.line.order.pk,
                'loan_order_reference': self.line.order.reference,
                'quantity': str(self.quantity),
            },
            notes=_('Item loaned out'),
        )

        # Update line item
        self.line.loaned_quantity += self.quantity
        self.line.status = LoanOrderLineStatus.LOANED.value
        self.line.save()

    def return_allocation(self, quantity, user=None, condition=None):
        """Return allocated stock item."""
        if quantity > self.quantity:
            raise ValidationError(_('Cannot return more than allocated'))

        self.item.add_tracking_entry(
            StockHistoryCode.RETURNED_FROM_LOAN,
            user,
            {
                'loan_order': self.line.order.pk,
                'loan_order_reference': self.line.order.reference,
                'returned_quantity': str(quantity),
                'condition': condition,
            },
            notes=_('Item returned from loan'),
        )

        # Update line item
        self.line.returned_quantity += quantity
        if self.line.returned_quantity >= self.line.loaned_quantity:
            self.line.status = LoanOrderLineStatus.RETURNED.value
        self.line.save()

        # If fully returned, delete allocation
        if quantity >= self.quantity:
            self.delete()
        else:
            self.quantity -= quantity
            self.save()


class LoanOrderTracking(InvenTree.models.InvenTreeModel):
    """Model for tracking history of loan orders."""

    order = models.ForeignKey(
        'loan.LoanOrder',
        on_delete=models.CASCADE,
        related_name='tracking',
        verbose_name=_('Loan Order'),
    )

    date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Date'),
    )

    tracking_type = models.IntegerField(
        choices=[(code.value, code.name) for code in LoanTrackingCode],
        verbose_name=_('Tracking Type'),
    )

    user = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_('User'),
    )

    notes = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Notes'),
    )

    class Meta:
        verbose_name = _('Loan Order Tracking')
        verbose_name_plural = _('Loan Order Tracking')
        ordering = ['-date']


class LoanOrderLineConversion(InvenTree.models.InvenTreeModel):
    """Model to track conversions from loan line to sales orders.

    Permits multiple conversions from the same loan line.
    """

    loan_line = models.ForeignKey(
        'loan.LoanOrderLineItem',
        on_delete=models.CASCADE,
        related_name='conversions',
        verbose_name=_('Loan Line'),
    )

    sales_order_line = models.ForeignKey(
        'order.SalesOrderLineItem',
        on_delete=models.CASCADE,
        related_name='converted_from_loan_lines',
        verbose_name=_('Sales Order Line'),
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
    )

    converted_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_('Converted By'),
    )

    is_returned_items = models.BooleanField(
        default=False,
        verbose_name=_('Is Returned Items'),
        help_text=_('Whether this conversion is from returned items'),
    )

    class Meta:
        verbose_name = _('Loan Order Line Conversion')
        verbose_name_plural = _('Loan Order Line Conversions')
        ordering = ['-converted_date']

    @property
    def sales_order(self):
        """Return the sales order for this conversion."""
        return self.sales_order_line.order
```

### 7. `src/backend/InvenTree/loan/serializers.py`

```python
"""Serializers for the loan app."""

from django.utils.translation import gettext_lazy as _

from rest_framework import serializers
from rest_framework.validators import MinValueValidator

import common.filters
from common.serializers import ProjectCodeSerializer
from company.serializers import ContactSerializer, AddressBriefSerializer, CompanyBriefSerializer
from InvenTree.serializers import (
    InvenTreeModelSerializer,
    InvenTreeCustomStatusSerializerMixin,
    InvenTreeModelMoneyField,
)
from users.serializers import OwnerSerializer, UserSerializer
from part.serializers import PartBriefSerializer
from stock.serializers import StockItemSerializer
from importer.mixins import DataImportExportSerializerMixin
from common.filters import FilterableSerializerMixin

from loan.models import (
    LoanOrder,
    LoanOrderLineItem,
    LoanOrderTracking,
    LoanOrderAllocation,
    LoanOrderLineConversion,
)
from loan.status_codes import LoanOrderStatus, LoanOrderLineStatus


class LoanOrderSerializer(
    DataImportExportSerializerMixin,
    FilterableSerializerMixin,
    InvenTreeCustomStatusSerializerMixin,
    InvenTreeModelSerializer,
):
    """Serializer for LoanOrder model."""

    class Meta:
        model = LoanOrder
        fields = [
            'pk',
            'reference',
            'borrower',
            'borrower_detail',
            'borrower_company',
            'borrower_company_detail',
            'contact',
            'contact_detail',
            'address',
            'address_detail',
            'status',
            'status_text',
            'status_custom_key',
            'creation_date',
            'requested_date',
            'issue_date',
            'due_date',
            'return_date',
            'created_by',
            'created_by_detail',
            'responsible',
            'responsible_detail',
            'issued_by',
            'issued_by_detail',
            'received_by',
            'received_by_detail',
            'project_code',
            'project_code_detail',
            'description',
            'notes',
            'barcode_hash',
            'line_items',
            'loaned_items',
            'returned_items',
            'overdue',
            'metadata',
            'parameters',
        ]
        read_only_fields = [
            'reference',
            'creation_date',
            'created_by',
            'barcode_hash',
            'line_items',
            'loaned_items',
            'returned_items',
            'overdue',
        ]

    borrower_detail = OwnerSerializer(source='borrower', read_only=True)
    borrower_company_detail = CompanyBriefSerializer(source='borrower_company', read_only=True)
    contact_detail = ContactSerializer(source='contact', read_only=True)
    address_detail = AddressBriefSerializer(source='address', read_only=True)
    responsible_detail = OwnerSerializer(source='responsible', read_only=True)
    created_by_detail = UserSerializer(source='created_by', read_only=True)
    issued_by_detail = UserSerializer(source='issued_by', read_only=True)
    received_by_detail = UserSerializer(source='received_by', read_only=True)
    project_code_detail = ProjectCodeSerializer(source='project_code', read_only=True)
    parameters = common.filters.enable_parameters_filter()

    line_items = serializers.IntegerField(read_only=True)
    loaned_items = serializers.DecimalField(max_digits=15, decimal_places=5, read_only=True)
    returned_items = serializers.DecimalField(max_digits=15, decimal_places=5, read_only=True)
    overdue = serializers.BooleanField(source='is_overdue', read_only=True)

    @staticmethod
    def annotate_queryset(queryset):
        """Add extra information to the queryset."""
        from django.db.models import Count, Sum

        queryset = queryset.annotate(
            line_items=Count('lines'),
            loaned_items=Sum('lines__loaned_quantity'),
            returned_items=Sum('lines__returned_quantity'),
        )
        queryset = queryset.select_related(
            'created_by',
            'borrower',
            'borrower_company',
            'contact',
            'address',
            'responsible',
        )
        return queryset


class LoanOrderLineItemSerializer(
    InvenTreeCustomStatusSerializerMixin,
    InvenTreeModelSerializer,
):
    """Serializer for LoanOrderLineItem model."""

    class Meta:
        model = LoanOrderLineItem
        fields = [
            'pk',
            'order',
            'order_detail',
            'part',
            'part_detail',
            'quantity',
            'loaned_quantity',
            'returned_quantity',
            'converted_quantity',
            'returned_and_sold_quantity',
            'status',
            'status_text',
            'reference',
            'notes',
            'target_date',
            'overdue',
            'remaining_loanable',
            'allocations',
        ]
        read_only_fields = [
            'loaned_quantity',
            'returned_quantity',
            'converted_quantity',
            'returned_and_sold_quantity',
            'overdue',
            'remaining_loanable',
        ]

    order_detail = LoanOrderSerializer(source='order', read_only=True, many=False)
    part_detail = PartBriefSerializer(source='part', read_only=True)
    overdue = serializers.BooleanField(source='is_overdue', read_only=True)
    remaining_loanable = serializers.DecimalField(
        source='get_remaining_loanable_quantity',
        max_digits=15,
        decimal_places=5,
        read_only=True,
    )
    allocations = serializers.IntegerField(source='allocations.count', read_only=True)


class LoanOrderAllocationSerializer(InvenTreeModelSerializer):
    """Serializer for LoanOrderAllocation model."""

    class Meta:
        model = LoanOrderAllocation
        fields = [
            'pk',
            'line',
            'item',
            'item_detail',
            'quantity',
            'is_converted',
        ]
        read_only_fields = ['is_converted']

    item_detail = StockItemSerializer(source='item', read_only=True)


class LoanOrderTrackingSerializer(InvenTreeModelSerializer):
    """Serializer for LoanOrderTracking model."""

    class Meta:
        model = LoanOrderTracking
        fields = [
            'pk',
            'order',
            'date',
            'tracking_type',
            'tracking_type_text',
            'user',
            'user_detail',
            'notes',
        ]
        read_only_fields = ['date']

    user_detail = UserSerializer(source='user', read_only=True)
    tracking_type_text = serializers.SerializerMethodField()

    def get_tracking_type_text(self, obj):
        """Return human-readable tracking type."""
        from loan.status_codes import LoanTrackingCode
        try:
            return LoanTrackingCode(obj.tracking_type).name.replace('_', ' ').title()
        except ValueError:
            return str(obj.tracking_type)


class LoanLineConvertSerializer(serializers.Serializer):
    """Serializer for converting loan line to sale."""

    quantity = serializers.DecimalField(
        max_digits=15,
        decimal_places=5,
        required=True,
        validators=[MinValueValidator(0)],
    )

    sale_price = InvenTreeModelMoneyField(
        max_digits=19,
        decimal_places=6,
        required=False,
        allow_null=True,
    )

    existing_sales_order = serializers.PrimaryKeyRelatedField(
        queryset=None,  # Set dynamically
        required=False,
        allow_null=True,
        help_text=_('Existing SalesOrder to add line to (optional)'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from order.models import SalesOrder
        self.fields['existing_sales_order'].queryset = SalesOrder.objects.all()

    def validate_quantity(self, value):
        """Validate conversion quantity."""
        line = self.context.get('line')
        if line:
            remaining = line.get_remaining_loanable_quantity()
            if value > remaining:
                raise serializers.ValidationError(
                    _('Cannot convert more than remaining quantity: {remaining}').format(
                        remaining=remaining
                    )
                )
        return value


class LoanLineSellReturnedSerializer(serializers.Serializer):
    """Serializer for selling returned items from loan line."""

    quantity = serializers.DecimalField(
        max_digits=15,
        decimal_places=5,
        required=True,
        validators=[MinValueValidator(0)],
    )

    sale_price = InvenTreeModelMoneyField(
        max_digits=19,
        decimal_places=6,
        required=False,
        allow_null=True,
    )

    existing_sales_order = serializers.PrimaryKeyRelatedField(
        queryset=None,
        required=False,
        allow_null=True,
        help_text=_('Existing SalesOrder to add line to (optional)'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from order.models import SalesOrder
        self.fields['existing_sales_order'].queryset = SalesOrder.objects.all()

    def validate_quantity(self, value):
        """Validate sale quantity."""
        line = self.context.get('line')
        if line:
            available_returned = line.returned_quantity - line.returned_and_sold_quantity
            if value > available_returned:
                raise serializers.ValidationError(
                    _('Cannot sell more than available returned quantity: {available}').format(
                        available=available_returned
                    )
                )
        return value


class LoanOrderAllocationItemSerializer(serializers.Serializer):
    """Serializer for a single loan allocation item."""

    line_item = serializers.PrimaryKeyRelatedField(
        queryset=LoanOrderLineItem.objects.all(),
        required=True,
    )

    stock_item = serializers.PrimaryKeyRelatedField(
        queryset=None,
        required=True,
    )

    quantity = serializers.DecimalField(
        max_digits=15,
        decimal_places=5,
        required=True,
        validators=[MinValueValidator(0)],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from stock.models import StockItem
        self.fields['stock_item'].queryset = StockItem.objects.all()

    def validate_line_item(self, line_item):
        """Validate line item belongs to order."""
        order = self.context.get('order')
        if order and line_item.order != order:
            raise serializers.ValidationError(_('Line item does not belong to this loan order'))
        return line_item

    def validate(self, data):
        """Validate allocation data."""
        line_item = data.get('line_item')
        stock_item = data.get('stock_item')
        quantity = data.get('quantity')

        if line_item and stock_item:
            # Check part matches
            if stock_item.part != line_item.part:
                raise serializers.ValidationError({
                    'stock_item': _('Stock item part does not match line item part')
                })

            # Check availability
            available = stock_item.unallocated_quantity()
            if quantity > available:
                raise serializers.ValidationError({
                    'quantity': _('Insufficient stock available. Available: {available}').format(
                        available=available
                    )
                })

        return data


class LoanOrderBulkAllocationSerializer(serializers.Serializer):
    """Serializer for allocating stock to loan order."""

    items = LoanOrderAllocationItemSerializer(many=True)

    def validate(self, data):
        """Validate allocation data."""
        items = data.get('items', [])
        if len(items) == 0:
            raise serializers.ValidationError(_('At least one allocation item must be provided'))
        return data

    def save(self):
        """Create allocations."""
        order = self.context['order']
        user = self.context['request'].user
        items = self.validated_data['items']

        allocations = []
        for item_data in items:
            line_item = item_data['line_item']
            stock_item = item_data['stock_item']
            quantity = item_data['quantity']

            allocation = line_item.allocate_stock(
                stock_item=stock_item,
                quantity=quantity,
                user=user
            )
            allocations.append(allocation)

        return allocations
```

### 8. `src/backend/InvenTree/loan/api.py`

```python
"""API views for the loan app."""

from django.utils.translation import gettext_lazy as _

from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from InvenTree.api import (
    ListCreateAPI,
    RetrieveUpdateDestroyAPI,
    CreateAPI,
    MetadataView,
    StatusView,
)
from InvenTree.mixins import (
    SerializerContextMixin,
    ParameterListMixin,
)
from order.serializers import SalesOrderSerializer
from importer.mixins import DataExportViewMixin
from InvenTree.filters import SEARCH_ORDER_FILTER

from loan.models import (
    LoanOrder,
    LoanOrderLineItem,
    LoanOrderTracking,
    LoanOrderAllocation,
)
from loan.serializers import (
    LoanOrderSerializer,
    LoanOrderLineItemSerializer,
    LoanOrderTrackingSerializer,
    LoanOrderAllocationSerializer,
    LoanLineConvertSerializer,
    LoanLineSellReturnedSerializer,
    LoanOrderBulkAllocationSerializer,
)
from loan.status_codes import LoanOrderStatus
from loan.filters import LoanOrderFilter, LoanOrderLineItemFilter


class LoanOrderList(
    SerializerContextMixin,
    DataExportViewMixin,
    ParameterListMixin,
    ListCreateAPI,
):
    """List and create API endpoint for LoanOrder model."""

    queryset = LoanOrder.objects.all()
    serializer_class = LoanOrderSerializer
    filterset_class = LoanOrderFilter

    role_required = 'loan_order.view'

    filter_backends = SEARCH_ORDER_FILTER

    search_fields = [
        'reference',
        'description',
        'borrower__name',
        'borrower_company__name',
        'contact__name',
    ]

    ordering_fields = [
        'reference',
        'creation_date',
        'due_date',
        'status',
    ]

    ordering = ['-creation_date']

    def get_queryset(self, *args, **kwargs):
        """Return annotated queryset."""
        queryset = super().get_queryset(*args, **kwargs)
        queryset = LoanOrderSerializer.annotate_queryset(queryset)
        return queryset

    def perform_create(self, serializer):
        """Create a new loan order."""
        serializer.save(created_by=self.request.user)


class LoanOrderDetail(
    SerializerContextMixin,
    RetrieveUpdateDestroyAPI,
):
    """Detail API endpoint for LoanOrder model."""

    queryset = LoanOrder.objects.all()
    serializer_class = LoanOrderSerializer

    role_required = 'loan_order.view'


class LoanOrderApprove(SerializerContextMixin, CreateAPI):
    """Approve a loan order (only superuser)."""

    queryset = LoanOrder.objects.all()
    serializer_class = LoanOrderSerializer

    def check_permissions(self, request):
        """Check that user is superuser."""
        if not request.user.is_superuser:
            raise PermissionDenied(_('Only superusers can approve loan orders'))
        return super().check_permissions(request)

    def create(self, request, *args, **kwargs):
        """Approve the loan order."""
        order = self.get_object()
        order.approve(user=request.user)
        return Response(
            LoanOrderSerializer(order).data,
            status=status.HTTP_200_OK
        )


class LoanOrderIssue(SerializerContextMixin, CreateAPI):
    """Issue a loan order."""

    queryset = LoanOrder.objects.all()
    serializer_class = LoanOrderSerializer

    role_required = 'loan_order.change'

    def create(self, request, *args, **kwargs):
        """Issue the loan order."""
        order = self.get_object()
        order.issue_loan(user=request.user)
        return Response(
            LoanOrderSerializer(order).data,
            status=status.HTTP_200_OK
        )


class LoanOrderComplete(SerializerContextMixin, CreateAPI):
    """Complete a loan order."""

    queryset = LoanOrder.objects.all()
    serializer_class = LoanOrderSerializer

    role_required = 'loan_order.change'

    def create(self, request, *args, **kwargs):
        """Complete the loan order."""
        order = self.get_object()
        order.complete_loan(user=request.user)
        return Response(
            LoanOrderSerializer(order).data,
            status=status.HTTP_200_OK
        )


class LoanOrderCancel(SerializerContextMixin, CreateAPI):
    """Cancel a loan order."""

    queryset = LoanOrder.objects.all()
    serializer_class = LoanOrderSerializer

    role_required = 'loan_order.change'

    def create(self, request, *args, **kwargs):
        """Cancel the loan order."""
        order = self.get_object()
        order.cancel(user=request.user)
        return Response(
            LoanOrderSerializer(order).data,
            status=status.HTTP_200_OK
        )


class LoanOrderAllocate(SerializerContextMixin, CreateAPI):
    """Allocate stock items to loan order."""

    queryset = LoanOrder.objects.all()
    serializer_class = LoanOrderBulkAllocationSerializer

    role_required = 'loan_order.change'

    def get_serializer_context(self):
        """Add order to serializer context."""
        context = super().get_serializer_context()
        context['order'] = self.get_object()
        return context

    def create(self, request, *args, **kwargs):
        """Allocate stock items to loan order."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        order = self.get_object()
        return Response(
            LoanOrderSerializer(order).data,
            status=status.HTTP_200_OK
        )


class LoanLineList(SerializerContextMixin, ListCreateAPI):
    """List and create API endpoint for LoanOrderLineItem model."""

    queryset = LoanOrderLineItem.objects.all()
    serializer_class = LoanOrderLineItemSerializer
    filterset_class = LoanOrderLineItemFilter

    role_required = 'loan_order.view'


class LoanLineDetail(SerializerContextMixin, RetrieveUpdateDestroyAPI):
    """Detail API endpoint for LoanOrderLineItem model."""

    queryset = LoanOrderLineItem.objects.all()
    serializer_class = LoanOrderLineItemSerializer

    role_required = 'loan_order.view'


class LoanLineReturn(SerializerContextMixin, CreateAPI):
    """Return items from a loan line."""

    queryset = LoanOrderLineItem.objects.all()
    serializer_class = LoanOrderLineItemSerializer

    role_required = 'loan_order.change'

    def create(self, request, *args, **kwargs):
        """Return items from loan."""
        line = self.get_object()
        quantity = request.data.get('quantity')
        condition = request.data.get('condition')

        if not quantity:
            return Response(
                {'quantity': _('Quantity is required')},
                status=status.HTTP_400_BAD_REQUEST
            )

        line.return_stock(
            quantity=float(quantity),
            user=request.user,
            condition=condition
        )

        return Response(
            LoanOrderLineItemSerializer(line).data,
            status=status.HTTP_200_OK
        )


class LoanLineConvertToSale(SerializerContextMixin, CreateAPI):
    """Convert loan line items to sales order."""

    queryset = LoanOrderLineItem.objects.all()
    serializer_class = LoanLineConvertSerializer

    role_required = 'loan_order.change'

    def get_serializer_context(self):
        """Add line to serializer context."""
        context = super().get_serializer_context()
        context['line'] = self.get_object()
        return context

    def create(self, request, *args, **kwargs):
        """Convert loan items to sale."""
        line = self.get_object()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quantity = serializer.validated_data['quantity']
        sale_price = serializer.validated_data.get('sale_price')
        existing_so = serializer.validated_data.get('existing_sales_order')

        sales_order = line.convert_to_sales_order(
            quantity=quantity,
            user=request.user,
            sale_price=sale_price,
            existing_sales_order=existing_so,
        )

        return Response(
            {
                'loan_line': LoanOrderLineItemSerializer(line).data,
                'sales_order': SalesOrderSerializer(sales_order).data,
                'message': _('Items converted to sales order successfully'),
            },
            status=status.HTTP_201_CREATED
        )


class LoanLineSellReturned(SerializerContextMixin, CreateAPI):
    """Sell returned items from loan line."""

    queryset = LoanOrderLineItem.objects.all()
    serializer_class = LoanLineSellReturnedSerializer

    role_required = 'loan_order.change'

    def get_serializer_context(self):
        """Add line to serializer context."""
        context = super().get_serializer_context()
        context['line'] = self.get_object()
        return context

    def create(self, request, *args, **kwargs):
        """Sell returned items."""
        line = self.get_object()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quantity = serializer.validated_data['quantity']
        sale_price = serializer.validated_data.get('sale_price')
        existing_so = serializer.validated_data.get('existing_sales_order')

        sales_order = line.sell_returned_items(
            quantity=quantity,
            user=request.user,
            sale_price=sale_price,
            existing_sales_order=existing_so,
        )

        return Response(
            {
                'loan_line': LoanOrderLineItemSerializer(line).data,
                'sales_order': SalesOrderSerializer(sales_order).data,
                'message': _('Returned items sold successfully'),
            },
            status=status.HTTP_201_CREATED
        )


class LoanTrackingList(SerializerContextMixin, ListCreateAPI):
    """List API endpoint for LoanOrderTracking model."""

    queryset = LoanOrderTracking.objects.all()
    serializer_class = LoanOrderTrackingSerializer

    role_required = 'loan_order.view'


class LoanTrackingDetail(SerializerContextMixin, RetrieveUpdateDestroyAPI):
    """Detail API endpoint for LoanOrderTracking model."""

    queryset = LoanOrderTracking.objects.all()
    serializer_class = LoanOrderTrackingSerializer

    role_required = 'loan_order.view'


class LoanAllocationList(SerializerContextMixin, ListCreateAPI):
    """List and create API endpoint for LoanOrderAllocation model."""

    queryset = LoanOrderAllocation.objects.all()
    serializer_class = LoanOrderAllocationSerializer

    role_required = 'loan_order.view'


class LoanAllocationDetail(SerializerContextMixin, RetrieveUpdateDestroyAPI):
    """Detail API endpoint for LoanOrderAllocation model."""

    queryset = LoanOrderAllocation.objects.all()
    serializer_class = LoanOrderAllocationSerializer

    role_required = 'loan_order.view'


# URL patterns
from django.urls import path, include

loan_api_urls = [
    # Loan Order endpoints
    path(
        'order/',
        include([
            path(
                '<int:pk>/',
                include([
                    path('complete/', LoanOrderComplete.as_view(), name='api-loan-order-complete'),
                    path('cancel/', LoanOrderCancel.as_view(), name='api-loan-order-cancel'),
                    path('approve/', LoanOrderApprove.as_view(), name='api-loan-order-approve'),
                    path('issue/', LoanOrderIssue.as_view(), name='api-loan-order-issue'),
                    path('allocate/', LoanOrderAllocate.as_view(), name='api-loan-order-allocate'),
                    path('metadata/', MetadataView.as_view(), {'model': LoanOrder}, name='api-loan-order-metadata'),
                    path('', LoanOrderDetail.as_view(), name='api-loan-order-detail'),
                ]),
            ),
            path('status/', StatusView.as_view(), {StatusView.MODEL_REF: LoanOrderStatus}, name='api-loan-order-status-codes'),
            path('', LoanOrderList.as_view(), name='api-loan-order-list'),
        ]),
    ),
    # Line Item endpoints
    path(
        'line/',
        include([
            path(
                '<int:pk>/',
                include([
                    path('convert-to-sale/', LoanLineConvertToSale.as_view(), name='api-loan-line-convert-to-sale'),
                    path('sell-returned/', LoanLineSellReturned.as_view(), name='api-loan-line-sell-returned'),
                    path('return/', LoanLineReturn.as_view(), name='api-loan-line-return'),
                    path('', LoanLineDetail.as_view(), name='api-loan-line-detail'),
                ]),
            ),
            path('', LoanLineList.as_view(), name='api-loan-line-list'),
        ]),
    ),
    # Allocation endpoints
    path(
        'allocation/',
        include([
            path('<int:pk>/', LoanAllocationDetail.as_view(), name='api-loan-allocation-detail'),
            path('', LoanAllocationList.as_view(), name='api-loan-allocation-list'),
        ]),
    ),
    # Tracking endpoints
    path(
        'tracking/',
        include([
            path('<int:pk>/', LoanTrackingDetail.as_view(), name='api-loan-tracking-detail'),
            path('', LoanTrackingList.as_view(), name='api-loan-tracking-list'),
        ]),
    ),
]
```

### 9. `src/backend/InvenTree/loan/admin.py`

```python
"""Admin interface for loan models."""

from django.contrib import admin

from loan.models import (
    LoanOrder,
    LoanOrderLineItem,
    LoanOrderTracking,
    LoanOrderAllocation,
    LoanOrderLineConversion,
)


@admin.register(LoanOrder)
class LoanOrderAdmin(admin.ModelAdmin):
    """Admin interface for LoanOrder model."""

    list_display = ['reference', 'borrower', 'borrower_company', 'status', 'creation_date', 'due_date', 'is_overdue']
    list_filter = ['status', 'creation_date', 'due_date']
    search_fields = ['reference', 'description']
    readonly_fields = ['reference', 'creation_date', 'created_by']


@admin.register(LoanOrderLineItem)
class LoanOrderLineItemAdmin(admin.ModelAdmin):
    """Admin interface for LoanOrderLineItem model."""

    list_display = ['order', 'part', 'quantity', 'loaned_quantity', 'returned_quantity', 'status']
    list_filter = ['status', 'order']
    search_fields = ['order__reference', 'part__name']


@admin.register(LoanOrderTracking)
class LoanOrderTrackingAdmin(admin.ModelAdmin):
    """Admin interface for LoanOrderTracking model."""

    list_display = ['order', 'date', 'tracking_type', 'user']
    list_filter = ['tracking_type', 'date']
    readonly_fields = ['date']


@admin.register(LoanOrderAllocation)
class LoanOrderAllocationAdmin(admin.ModelAdmin):
    """Admin interface for LoanOrderAllocation model."""

    list_display = ['line', 'item', 'quantity', 'is_converted']
    list_filter = ['is_converted']


@admin.register(LoanOrderLineConversion)
class LoanOrderLineConversionAdmin(admin.ModelAdmin):
    """Admin interface for LoanOrderLineConversion model."""

    list_display = ['loan_line', 'sales_order_line', 'quantity', 'converted_date', 'converted_by']
    list_filter = ['converted_date', 'is_returned_items']
```

### 10. `src/backend/InvenTree/loan/filters.py`

```python
"""Filter definitions for loan models."""

import django_filters
from django.db.models import Q
from django.utils import timezone

from loan.models import LoanOrder, LoanOrderLineItem
from loan.status_codes import LoanOrderStatusGroups


class LoanOrderFilter(django_filters.FilterSet):
    """Filter for LoanOrder model."""

    class Meta:
        model = LoanOrder
        fields = ['status', 'borrower', 'borrower_company', 'responsible', 'due_date']

    overdue = django_filters.BooleanFilter(method='filter_overdue')

    def filter_overdue(self, queryset, name, value):
        """Filter overdue loans.

        NOTE: OVERDUE is a computed property, not a status value.
        This filter checks: due_date < today AND status in OPEN
        """
        if value:
            today = timezone.now().date()
            return queryset.filter(
                due_date__lt=today,
                status__in=LoanOrderStatusGroups.OPEN
            )
        return queryset


class LoanOrderLineItemFilter(django_filters.FilterSet):
    """Filter for LoanOrderLineItem model."""

    class Meta:
        model = LoanOrderLineItem
        fields = ['order', 'part', 'status']
```

### 11. `src/backend/InvenTree/loan/tasks.py`

```python
"""Background tasks for the loan app."""

from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from InvenTree.tasks import scheduled_task, ScheduledTask
from common.notifications import trigger_notification
from InvenTree.helpers_model import construct_absolute_url
from plugin.events import trigger_event

from loan.models import LoanOrder, LoanOrderTracking
from loan.status_codes import LoanOrderStatusGroups, LoanTrackingCode
from loan.events import LoanOrderEvents


@scheduled_task(ScheduledTask.DAILY)
def check_overdue_loans():
    """Check for loans that became overdue yesterday and send notifications.

    NOTE: This task sends notifications for loans that crossed their due date.
    It does NOT change the loan status - OVERDUE is a computed property.
    """
    yesterday = timezone.now().date() - timedelta(days=1)

    newly_overdue_loans = LoanOrder.objects.filter(
        due_date=yesterday,
        status__in=LoanOrderStatusGroups.OPEN,
    )

    for loan in newly_overdue_loans:
        notify_overdue_loan(loan)


def notify_overdue_loan(loan: LoanOrder):
    """Notify users about an overdue loan."""
    targets = []

    if loan.created_by:
        targets.append(loan.created_by)

    if loan.responsible:
        targets.append(loan.responsible)

    if loan.borrower:
        if hasattr(loan.borrower, 'owner') and hasattr(loan.borrower.owner, 'email'):
            targets.append(loan.borrower.owner)

    targets.extend(loan.subscribed_users())

    context = {
        'loan': loan,
        'name': _('Overdue Loan'),
        'message': _('Loan {reference} is now overdue').format(reference=loan.reference),
        'link': construct_absolute_url(loan.get_absolute_url()),
        'template': {
            'html': 'email/overdue_loan.html',
            'subject': _('Overdue Loan'),
        },
    }

    trigger_notification(
        loan,
        LoanOrderEvents.OVERDUE,
        targets=targets,
        context=context,
    )

    trigger_event(LoanOrderEvents.OVERDUE, loan_order=loan.pk)

    # Create tracking entry for notification
    LoanOrderTracking.objects.create(
        order=loan,
        tracking_type=LoanTrackingCode.OVERDUE_NOTIFIED,
        notes=_('Overdue notification sent'),
    )
```

### 12. `src/backend/InvenTree/loan/fixtures/loan.yaml`

```yaml
- model: loan.loanorder
  pk: 1
  fields:
    reference: LOAN-0001
    borrower: 1
    description: Test loan order
    due_date: 2025-12-31
    status: 10
    creation_date: 2025-01-01
    created_by: 1

- model: loan.loanorderlineitem
  pk: 1
  fields:
    order: 1
    part: 1
    quantity: 5.00000
    loaned_quantity: 0.00000
    returned_quantity: 0.00000
    status: 10
```

---

## Frontend Files to Create

### 1. `src/frontend/src/pages/loans/LoansIndex.tsx`

```typescript
import { Stack } from '@mantine/core';
import { t } from '@lingui/macro';

import { PageDetail } from '../../components/nav/PageDetail';
import { LoanOrderTable } from '../../tables/loans/LoanOrderTable';

export default function LoansIndex() {
  return (
    <Stack gap="xs">
      <PageDetail
        title={t`Loans`}
        breadcrumbs={[{ name: t`Home`, url: '/' }]}
      />
      <LoanOrderTable />
    </Stack>
  );
}
```

### 2. `src/frontend/src/pages/loans/LoanOrderDetail.tsx`

```typescript
import { useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Stack, Badge, Group, Text, Alert } from '@mantine/core';
import { t } from '@lingui/macro';
import {
  IconInfoCircle,
  IconList,
  IconHistory,
  IconPaperclip,
  IconPackage,
  IconAlertTriangle,
} from '@tabler/icons-react';

import { PageDetail } from '../../components/nav/PageDetail';
import { PanelGroup, PanelType } from '../../components/nav/PanelGroup';
import { InstanceDetail } from '../../components/items/InstanceDetail';
import { AttachmentTable } from '../../tables/general/AttachmentTable';
import { useInstance } from '../../hooks/UseInstance';
import { ApiEndpoints } from '../../lib/enums/ApiEndpoints';
import { ModelType } from '../../lib/enums/ModelType';
import { StatusRenderer } from '../../components/render/StatusRenderer';
import { ActionDropdown } from '../../components/items/ActionDropdown';
import { useCreateApiFormModal, useEditApiFormModal } from '../../hooks/UseForm';
import { loanOrderFields } from '../../forms/LoanForms';

import { LoanOrderLineItemTable } from '../../tables/loans/LoanOrderLineItemTable';
import { LoanOrderAllocationTable } from '../../tables/loans/LoanOrderAllocationTable';
import { LoanOrderTrackingTable } from '../../tables/loans/LoanOrderTrackingTable';

export default function LoanOrderDetail() {
  const { id } = useParams();
  const navigate = useNavigate();

  const {
    instance: loanOrder,
    instanceQuery,
    refreshInstance,
  } = useInstance({
    endpoint: ApiEndpoints.loan_order_list,
    pk: id,
    refetchOnMount: true,
  });

  const loanOrderActions = useMemo(() => {
    const actions = [];

    // Approve action (only for pending orders)
    if (loanOrder?.status === 10) {
      actions.push({
        name: 'approve',
        label: t`Approve`,
        icon: <IconInfoCircle />,
        onClick: () => {
          // Call approve API
        },
      });
    }

    // Issue action (only for approved orders)
    if (loanOrder?.status === 20) {
      actions.push({
        name: 'issue',
        label: t`Issue`,
        icon: <IconPackage />,
        onClick: () => {
          // Call issue API
        },
      });
    }

    // Complete action (only for issued/partial return orders)
    if ([30, 40].includes(loanOrder?.status)) {
      actions.push({
        name: 'complete',
        label: t`Complete`,
        icon: <IconInfoCircle />,
        onClick: () => {
          // Call complete API
        },
      });
    }

    // Cancel action (not for completed/cancelled orders)
    if (![50, 60].includes(loanOrder?.status)) {
      actions.push({
        name: 'cancel',
        label: t`Cancel`,
        icon: <IconAlertTriangle />,
        color: 'red',
        onClick: () => {
          // Call cancel API
        },
      });
    }

    return actions;
  }, [loanOrder]);

  const panels: PanelType[] = useMemo(() => [
    {
      name: 'details',
      label: t`Loan Details`,
      icon: <IconInfoCircle />,
      content: (
        <Stack gap="md">
          {loanOrder?.overdue && (
            <Alert color="red" icon={<IconAlertTriangle />}>
              {t`This loan is overdue!`}
            </Alert>
          )}
          <Group>
            <Text fw={500}>{t`Status`}:</Text>
            <StatusRenderer status={loanOrder?.status} type={ModelType.loanorder} />
          </Group>
          <Group>
            <Text fw={500}>{t`Borrower`}:</Text>
            <Text>{loanOrder?.borrower_detail?.name}</Text>
          </Group>
          {loanOrder?.borrower_company_detail && (
            <Group>
              <Text fw={500}>{t`Borrower Company`}:</Text>
              <Text>{loanOrder?.borrower_company_detail?.name}</Text>
            </Group>
          )}
          <Group>
            <Text fw={500}>{t`Due Date`}:</Text>
            <Text>{loanOrder?.due_date}</Text>
          </Group>
          <Group>
            <Text fw={500}>{t`Description`}:</Text>
            <Text>{loanOrder?.description}</Text>
          </Group>
        </Stack>
      ),
    },
    {
      name: 'lines',
      label: t`Line Items`,
      icon: <IconList />,
      content: <LoanOrderLineItemTable orderId={id} refreshOrder={refreshInstance} />,
    },
    {
      name: 'allocations',
      label: t`Allocations`,
      icon: <IconPackage />,
      content: <LoanOrderAllocationTable orderId={id} />,
    },
    {
      name: 'tracking',
      label: t`Tracking`,
      icon: <IconHistory />,
      content: <LoanOrderTrackingTable orderId={id} />,
    },
    {
      name: 'attachments',
      label: t`Attachments`,
      icon: <IconPaperclip />,
      content: <AttachmentTable modelType={ModelType.loanorder} modelId={Number(id)} />,
    },
  ], [loanOrder, id, refreshInstance]);

  return (
    <InstanceDetail query={instanceQuery}>
      <PageDetail
        title={`${t`Loan`}: ${loanOrder?.reference}`}
        subtitle={loanOrder?.description}
        breadcrumbs={[
          { name: t`Loans`, url: '/loans/' },
        ]}
        actions={[
          <ActionDropdown
            key="actions"
            actions={loanOrderActions}
          />,
        ]}
        badges={[
          loanOrder?.overdue && (
            <Badge key="overdue" color="red">
              {t`Overdue`}
            </Badge>
          ),
        ].filter(Boolean)}
      />
      <PanelGroup
        pageKey="loan-order"
        panels={panels}
        model={ModelType.loanorder}
        id={Number(id)}
        instance={loanOrder}
      />
    </InstanceDetail>
  );
}
```

### 3. `src/frontend/src/tables/loans/LoanOrderTable.tsx`

```typescript
import { useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge } from '@mantine/core';
import { t } from '@lingui/macro';

import { InvenTreeTable } from '../InvenTreeTable';
import { useTable } from '../../hooks/UseTable';
import { useTableColumn } from '../../hooks/UseTableColumn';
import { ApiEndpoints } from '../../lib/enums/ApiEndpoints';
import { ModelType } from '../../lib/enums/ModelType';
import { StatusRenderer } from '../../components/render/StatusRenderer';
import { DateRenderer } from '../../components/render/DateRenderer';
import { useCreateApiFormModal } from '../../hooks/UseForm';
import { loanOrderFields } from '../../forms/LoanForms';

interface LoanOrderTableProps {
  params?: Record<string, any>;
}

export function LoanOrderTable({ params }: LoanOrderTableProps) {
  const navigate = useNavigate();
  const table = useTable('loan-order');

  const columns = useMemo(() => [
    {
      accessor: 'reference',
      title: t`Reference`,
      sortable: true,
      render: (record: any) => record.reference,
    },
    {
      accessor: 'borrower_detail.name',
      title: t`Borrower`,
      sortable: true,
      render: (record: any) => record.borrower_detail?.name,
    },
    {
      accessor: 'borrower_company_detail.name',
      title: t`Company`,
      sortable: true,
      render: (record: any) => record.borrower_company_detail?.name || '-',
    },
    {
      accessor: 'status',
      title: t`Status`,
      render: (record: any) => (
        <StatusRenderer status={record.status} type={ModelType.loanorder} />
      ),
    },
    {
      accessor: 'due_date',
      title: t`Due Date`,
      sortable: true,
      render: (record: any) => <DateRenderer value={record.due_date} />,
    },
    {
      accessor: 'overdue',
      title: t`Overdue`,
      render: (record: any) => (
        record.overdue ? <Badge color="red">{t`Overdue`}</Badge> : null
      ),
    },
    {
      accessor: 'line_items',
      title: t`Lines`,
      sortable: true,
    },
  ], []);

  const newLoanOrder = useCreateApiFormModal({
    url: ApiEndpoints.loan_order_list,
    title: t`Create Loan Order`,
    fields: loanOrderFields(),
    onFormSuccess: (data: any) => {
      table.refreshTable();
      navigate(`/loans/order/${data.pk}/`);
    },
  });

  const tableActions = useMemo(() => [
    {
      label: t`Add Loan Order`,
      onClick: () => newLoanOrder.open(),
    },
  ], [newLoanOrder]);

  const rowActions = useCallback((record: any) => [
    {
      title: t`View Details`,
      onClick: () => navigate(`/loans/order/${record.pk}/`),
    },
  ], [navigate]);

  return (
    <>
      {newLoanOrder.modal}
      <InvenTreeTable
        url={ApiEndpoints.loan_order_list}
        tableState={table}
        columns={columns}
        props={{
          params: params,
          tableActions: tableActions,
          rowActions: rowActions,
          onRowClick: (record: any) => navigate(`/loans/order/${record.pk}/`),
        }}
      />
    </>
  );
}
```

### 4. `src/frontend/src/tables/loans/LoanOrderLineItemTable.tsx`

```typescript
import { useMemo, useCallback } from 'react';
import { Badge, Group, ActionIcon, Tooltip } from '@mantine/core';
import { t } from '@lingui/macro';
import { IconShoppingCart, IconArrowBack, IconCoin } from '@tabler/icons-react';

import { InvenTreeTable } from '../InvenTreeTable';
import { useTable } from '../../hooks/UseTable';
import { ApiEndpoints } from '../../lib/enums/ApiEndpoints';
import { ModelType } from '../../lib/enums/ModelType';
import { StatusRenderer } from '../../components/render/StatusRenderer';
import { PartColumn } from '../../components/tables/PartColumn';
import { useCreateApiFormModal } from '../../hooks/UseForm';
import { loanLineItemFields, loanLineConvertFields, loanLineReturnFields, loanLineSellReturnedFields } from '../../forms/LoanForms';

interface LoanOrderLineItemTableProps {
  orderId: string | undefined;
  refreshOrder?: () => void;
}

export function LoanOrderLineItemTable({ orderId, refreshOrder }: LoanOrderLineItemTableProps) {
  const table = useTable('loan-order-line');

  const columns = useMemo(() => [
    {
      accessor: 'part_detail',
      title: t`Part`,
      render: (record: any) => <PartColumn part={record.part_detail} />,
    },
    {
      accessor: 'quantity',
      title: t`Quantity`,
      sortable: true,
    },
    {
      accessor: 'loaned_quantity',
      title: t`Loaned`,
    },
    {
      accessor: 'returned_quantity',
      title: t`Returned`,
    },
    {
      accessor: 'converted_quantity',
      title: t`Converted`,
    },
    {
      accessor: 'remaining_loanable',
      title: t`Remaining`,
    },
    {
      accessor: 'status',
      title: t`Status`,
      render: (record: any) => (
        <StatusRenderer status={record.status} type={ModelType.loanorderlineitem} />
      ),
    },
    {
      accessor: 'overdue',
      title: t`Overdue`,
      render: (record: any) => (
        record.overdue ? <Badge color="red" size="xs">{t`Overdue`}</Badge> : null
      ),
    },
  ], []);

  // Return items modal
  const returnModal = useCreateApiFormModal({
    url: ApiEndpoints.loan_line_return,
    pk: undefined,
    title: t`Return Items`,
    fields: loanLineReturnFields(),
    onFormSuccess: () => {
      table.refreshTable();
      refreshOrder?.();
    },
  });

  // Convert to sale modal
  const convertModal = useCreateApiFormModal({
    url: ApiEndpoints.loan_line_convert_to_sale,
    pk: undefined,
    title: t`Convert to Sale`,
    fields: loanLineConvertFields(),
    onFormSuccess: () => {
      table.refreshTable();
      refreshOrder?.();
    },
  });

  // Sell returned items modal
  const sellReturnedModal = useCreateApiFormModal({
    url: ApiEndpoints.loan_line_sell_returned,
    pk: undefined,
    title: t`Sell Returned Items`,
    fields: loanLineSellReturnedFields(),
    onFormSuccess: () => {
      table.refreshTable();
      refreshOrder?.();
    },
  });

  const rowActions = useCallback((record: any) => {
    const actions = [];

    // Return action (if items are loaned)
    if (record.loaned_quantity > record.returned_quantity) {
      actions.push({
        title: t`Return Items`,
        icon: <IconArrowBack size={16} />,
        onClick: () => returnModal.open({ pk: record.pk }),
      });
    }

    // Convert to sale action (if remaining loanable quantity exists)
    if (record.remaining_loanable > 0) {
      actions.push({
        title: t`Convert to Sale`,
        icon: <IconShoppingCart size={16} />,
        onClick: () => convertModal.open({ pk: record.pk }),
      });
    }

    // Sell returned items action (if returned items available)
    const returnedNotSold = record.returned_quantity - record.returned_and_sold_quantity;
    if (returnedNotSold > 0) {
      actions.push({
        title: t`Sell Returned Items`,
        icon: <IconCoin size={16} />,
        onClick: () => sellReturnedModal.open({ pk: record.pk }),
      });
    }

    return actions;
  }, [returnModal, convertModal, sellReturnedModal]);

  const newLineItem = useCreateApiFormModal({
    url: ApiEndpoints.loan_line_list,
    title: t`Add Line Item`,
    fields: loanLineItemFields(),
    initialData: { order: orderId },
    onFormSuccess: () => {
      table.refreshTable();
      refreshOrder?.();
    },
  });

  const tableActions = useMemo(() => [
    {
      label: t`Add Line Item`,
      onClick: () => newLineItem.open(),
    },
  ], [newLineItem]);

  return (
    <>
      {newLineItem.modal}
      {returnModal.modal}
      {convertModal.modal}
      {sellReturnedModal.modal}
      <InvenTreeTable
        url={ApiEndpoints.loan_line_list}
        tableState={table}
        columns={columns}
        props={{
          params: { order: orderId },
          tableActions: tableActions,
          rowActions: rowActions,
        }}
      />
    </>
  );
}
```

### 5. `src/frontend/src/tables/loans/LoanOrderAllocationTable.tsx`

```typescript
import { useMemo } from 'react';
import { Badge } from '@mantine/core';
import { t } from '@lingui/macro';

import { InvenTreeTable } from '../InvenTreeTable';
import { useTable } from '../../hooks/UseTable';
import { ApiEndpoints } from '../../lib/enums/ApiEndpoints';

interface LoanOrderAllocationTableProps {
  orderId: string | undefined;
}

export function LoanOrderAllocationTable({ orderId }: LoanOrderAllocationTableProps) {
  const table = useTable('loan-order-allocation');

  const columns = useMemo(() => [
    {
      accessor: 'line',
      title: t`Line`,
    },
    {
      accessor: 'item_detail.part_detail.name',
      title: t`Part`,
    },
    {
      accessor: 'item_detail.serial',
      title: t`Serial`,
    },
    {
      accessor: 'quantity',
      title: t`Quantity`,
    },
    {
      accessor: 'is_converted',
      title: t`Converted`,
      render: (record: any) => (
        record.is_converted ? <Badge color="blue">{t`Converted`}</Badge> : null
      ),
    },
  ], []);

  return (
    <InvenTreeTable
      url={ApiEndpoints.loan_allocation_list}
      tableState={table}
      columns={columns}
      props={{
        params: { order: orderId },
      }}
    />
  );
}
```

### 6. `src/frontend/src/tables/loans/LoanOrderTrackingTable.tsx`

```typescript
import { useMemo } from 'react';
import { t } from '@lingui/macro';

import { InvenTreeTable } from '../InvenTreeTable';
import { useTable } from '../../hooks/UseTable';
import { ApiEndpoints } from '../../lib/enums/ApiEndpoints';
import { DateRenderer } from '../../components/render/DateRenderer';

interface LoanOrderTrackingTableProps {
  orderId: string | undefined;
}

export function LoanOrderTrackingTable({ orderId }: LoanOrderTrackingTableProps) {
  const table = useTable('loan-order-tracking');

  const columns = useMemo(() => [
    {
      accessor: 'date',
      title: t`Date`,
      render: (record: any) => <DateRenderer value={record.date} />,
      sortable: true,
    },
    {
      accessor: 'tracking_type_text',
      title: t`Type`,
    },
    {
      accessor: 'user_detail.username',
      title: t`User`,
    },
    {
      accessor: 'notes',
      title: t`Notes`,
    },
  ], []);

  return (
    <InvenTreeTable
      url={ApiEndpoints.loan_tracking_list}
      tableState={table}
      columns={columns}
      props={{
        params: { order: orderId },
      }}
    />
  );
}
```

### 7. `src/frontend/src/forms/LoanForms.tsx`

```typescript
import { t } from '@lingui/macro';
import { ApiFormFieldSet } from '../components/forms/fields/ApiFormField';
import { ApiEndpoints } from '../lib/enums/ApiEndpoints';

export function loanOrderFields(): ApiFormFieldSet {
  return {
    borrower: {
      label: t`Borrower`,
      description: t`User or group borrowing items`,
    },
    borrower_company: {
      label: t`Borrower Company`,
      description: t`Company borrowing items (optional)`,
    },
    description: {
      label: t`Description`,
    },
    due_date: {
      label: t`Due Date`,
    },
    responsible: {
      label: t`Responsible`,
      description: t`User or group responsible for this loan`,
    },
    project_code: {
      label: t`Project Code`,
    },
    contact: {
      label: t`Contact`,
    },
    address: {
      label: t`Address`,
    },
    notes: {
      label: t`Notes`,
    },
  };
}

export function loanLineItemFields(): ApiFormFieldSet {
  return {
    order: {
      hidden: true,
    },
    part: {
      label: t`Part`,
    },
    quantity: {
      label: t`Quantity`,
    },
    reference: {
      label: t`Reference`,
    },
    target_date: {
      label: t`Target Date`,
    },
    notes: {
      label: t`Notes`,
    },
  };
}

export function loanLineReturnFields(): ApiFormFieldSet {
  return {
    quantity: {
      label: t`Quantity to Return`,
    },
    condition: {
      label: t`Condition`,
      description: t`Condition of returned items`,
    },
  };
}

export function loanLineConvertFields(): ApiFormFieldSet {
  return {
    quantity: {
      label: t`Quantity to Convert`,
    },
    sale_price: {
      label: t`Sale Price`,
      description: t`Price per unit`,
    },
    existing_sales_order: {
      label: t`Existing Sales Order`,
      description: t`Add to existing order instead of creating new one`,
    },
  };
}

export function loanLineSellReturnedFields(): ApiFormFieldSet {
  return {
    quantity: {
      label: t`Quantity to Sell`,
    },
    sale_price: {
      label: t`Sale Price`,
      description: t`Price per unit`,
    },
    existing_sales_order: {
      label: t`Existing Sales Order`,
      description: t`Add to existing order instead of creating new one`,
    },
  };
}

export function loanAllocationFields(): ApiFormFieldSet {
  return {
    line_item: {
      label: t`Line Item`,
    },
    stock_item: {
      label: t`Stock Item`,
    },
    quantity: {
      label: t`Quantity`,
    },
  };
}
```

---

## Files to Modify

### Backend Files to Modify

#### 1. `src/backend/InvenTree/InvenTree/settings.py`

**Location**: Around line 288 (after `order.apps.OrderConfig`)

**Add**:
```python
    'loan.apps.LoanConfig',
```

#### 2. `src/backend/InvenTree/InvenTree/urls.py`

**Location**: Around line 61 (in `apipatterns` list, after `order/`)

**Add**:
```python
    path('loan/', include(loan.api.loan_api_urls)),
```

**Also add import at top**:
```python
import loan.api
```

#### 3. `src/backend/InvenTree/users/ruleset.py`

**Location**: In `RuleSetEnum` class (around line 20)

**Add**:
```python
    LOAN_ORDER = 'loan_order'
```

**Location**: In `RULESET_CHOICES` list (around line 34)

**Add**:
```python
    (RuleSetEnum.LOAN_ORDER, _('Loan Orders')),
```

**Location**: In `get_ruleset_models()` function (around line 150)

**Add**:
```python
        RuleSetEnum.LOAN_ORDER: [
            'loan_loanorder',
            'loan_loanorderlineitem',
            'loan_loanordertracking',
            'loan_loanorderallocation',
            'loan_loanorderlineconversion',
            'stock_stockitem',
            'users_owner',
        ],
```

#### 4. `tasks.py`

**Location**: In `apps()` function (around line 259)

**Add**:
```python
        'loan',
```

#### 5. `src/backend/InvenTree/stock/status_codes.py`

**Location**: In `StockHistoryCode` class (around line 98)

**Add**:
```python
    # Loan order codes
    LOANED_OUT = 110, _('Loaned out')
    RETURNED_FROM_LOAN = 115, _('Returned from loan')
    CONVERTED_FROM_LOAN_TO_SALE = 120, _('Converted from loan to sale')
```

#### 6. `src/backend/InvenTree/stock/models.py`

**Location**: In `StockItem` class (add new method and modify `allocation_count`)

**Add**:
```python
    def loan_allocation_count(self, exclude_allocations=None):
        """Return the total quantity allocated to loan orders."""
        from loan.models import LoanOrderAllocation
        from loan.status_codes import LoanOrderStatusGroups
        from django.db.models import Sum

        allocations = LoanOrderAllocation.objects.filter(
            item=self,
            line__order__status__in=LoanOrderStatusGroups.OPEN
        )

        if exclude_allocations:
            allocations = allocations.exclude(**exclude_allocations)

        total = allocations.aggregate(total=Sum('quantity'))['total'] or Decimal(0)
        return total
```

**Modify `allocation_count()` method to include loan allocations**:
```python
    def allocation_count(self):
        """Return the total quantity allocated to builds, sales orders, and loans."""
        return (
            self.build_allocation_count() +
            self.sales_order_allocation_count() +
            self.loan_allocation_count()
        )
```

#### 7. `src/backend/InvenTree/common/setting/system.py`

**Location**: In `SYSTEM_SETTINGS` dictionary

**Add**:
```python
    'LOAN_ORDER_REFERENCE_PATTERN': {
        'name': _('Loan Order Reference Pattern'),
        'description': _('Pattern for generating loan order reference numbers'),
        'default': 'LOAN-{ref:04d}',
        'validator': loan.validators.validate_loan_order_reference_pattern,
    },
```

**Also add import at top**:
```python
import loan.validators
```

#### 8. `src/backend/InvenTree/order/models.py`

**Location**: In `SalesOrderShipment.clean()` method (around line 2223)

**Modify** to handle `customer=None`:
```python
if self.order and self.shipment_address:
    if self.order.customer and self.shipment_address.company != self.order.customer:
        raise ValidationError({
            'shipment_address': _('Shipment address must match the customer')
        })
```

#### 9. Report Templates

**Files**:
- `src/backend/InvenTree/report/templates/report/inventree_sales_order_report.html`
- `src/backend/InvenTree/report/templates/report/inventree_sales_order_shipment_report.html`

**Add** `{% if customer %}` checks around customer-related content:
```html
{% if customer %}
    <img class='logo' src='{% company_image customer %}' alt="{{ customer }}" width='150'>
{% endif %}

{% if customer %}
    {{ customer.name }}
{% else %}
    {% trans "No Customer" %}
{% endif %}
```

### Frontend Files to Modify

#### 1. `src/frontend/lib/enums/ApiEndpoints.tsx`

**Add**:
```typescript
  // Loan API endpoints
  loan_order_list = 'loan/order/',
  loan_order_detail = 'loan/order/:id/',
  loan_order_issue = 'loan/order/:id/issue/',
  loan_order_complete = 'loan/order/:id/complete/',
  loan_order_cancel = 'loan/order/:id/cancel/',
  loan_order_approve = 'loan/order/:id/approve/',
  loan_order_allocate = 'loan/order/:id/allocate/',
  loan_line_list = 'loan/line/',
  loan_line_detail = 'loan/line/:id/',
  loan_line_return = 'loan/line/:id/return/',
  loan_line_convert_to_sale = 'loan/line/:id/convert-to-sale/',
  loan_line_sell_returned = 'loan/line/:id/sell-returned/',
  loan_allocation_list = 'loan/allocation/',
  loan_allocation_detail = 'loan/allocation/:id/',
  loan_tracking_list = 'loan/tracking/',
  loan_tracking_detail = 'loan/tracking/:id/',
```

#### 2. `src/frontend/lib/enums/ModelType.tsx`

**Add**:
```typescript
  loanorder = 'loanorder',
  loanorderlineitem = 'loanorderlineitem',
  loanordertracking = 'loanordertracking',
  loanorderallocation = 'loanorderallocation',
```

#### 3. `src/frontend/src/router.tsx`

**Add lazy-loaded components**:
```typescript
export const LoansIndex = Loadable(
  lazy(() => import('./pages/loans/LoansIndex'))
);

export const LoanOrderDetail = Loadable(
  lazy(() => import('./pages/loans/LoanOrderDetail'))
);
```

**Add routes**:
```typescript
<Route path="/loans/" element={<LoansIndex />} />
<Route path="/loans/order/:id/" element={<LoanOrderDetail />} />
```

#### 4. `src/frontend/lib/enums/ModelInformation.tsx`

**Add**:
```typescript
  [ModelType.loanorder]: {
    label: () => t`Loan Order`,
    label_multiple: () => t`Loan Orders`,
    url_overview: '/loans/',
    url_detail: '/loans/order/:id/',
    api_endpoint: ApiEndpoints.loan_order_list,
    icon: 'loans',
  },
  [ModelType.loanorderlineitem]: {
    label: () => t`Loan Order Line Item`,
    label_multiple: () => t`Loan Order Line Items`,
    api_endpoint: ApiEndpoints.loan_line_list,
    icon: 'list',
  },
  [ModelType.loanordertracking]: {
    label: () => t`Loan Order Tracking`,
    label_multiple: () => t`Loan Order Tracking`,
    api_endpoint: ApiEndpoints.loan_tracking_list,
    icon: 'history',
  },
  [ModelType.loanorderallocation]: {
    label: () => t`Loan Order Allocation`,
    label_multiple: () => t`Loan Order Allocations`,
    api_endpoint: ApiEndpoints.loan_allocation_list,
    icon: 'package',
  },
```

---

## Testing Information

### Test Scenarios

#### 1. Create Loan Order

**Endpoint**: `POST /api/loan/order/`

**Body**:
```json
{
  "borrower": 1,
  "borrower_company": 1,
  "description": "Test loan order",
  "due_date": "2025-12-31",
  "responsible": 1
}
```

**Expected Response**: `201 Created`

#### 2. Add Line Item

**Endpoint**: `POST /api/loan/line/`

**Body**:
```json
{
  "order": 1,
  "part": 1,
  "quantity": "5.00000"
}
```

#### 3. Allocate Stock

**Endpoint**: `POST /api/loan/order/1/allocate/`

**Body**:
```json
{
  "items": [
    {
      "line_item": 1,
      "stock_item": 1,
      "quantity": "5.00000"
    }
  ]
}
```

#### 4. Issue Loan Order

**Endpoint**: `POST /api/loan/order/1/issue/`

#### 5. Return Items

**Endpoint**: `POST /api/loan/line/1/return/`

**Body**:
```json
{
  "quantity": "3.00000"
}
```

#### 6. Convert to Sale

**Endpoint**: `POST /api/loan/line/1/convert-to-sale/`

**Body**:
```json
{
  "quantity": "2.00000",
  "sale_price": "10.50"
}
```

#### 7. Sell Returned Items

**Endpoint**: `POST /api/loan/line/1/sell-returned/`

**Body**:
```json
{
  "quantity": "1.00000",
  "sale_price": "10.50"
}
```

### Testing Checklist

- [ ] Create loan order
- [ ] Add line items
- [ ] Allocate stock items (check unallocated_quantity validation)
- [ ] Approve loan order (superuser only)
- [ ] Issue loan order
- [ ] Return items (partial and full)
- [ ] Convert loan items to sale (new and existing SalesOrder)
- [ ] Sell returned items
- [ ] Complete loan order
- [ ] Cancel loan order
- [ ] Verify overdue detection (computed property, not status)
- [ ] Verify state machine transitions
- [ ] Test permissions
- [ ] Frontend pages and tables
- [ ] Frontend forms and modals

---

## Implementation Notes

### Critical Points

1. **OVERDUE is a Property**: OVERDUE is NOT a status value. It's computed via `is_overdue` property based on `due_date < today AND status in OPEN`.

2. **State Machine**: Status transitions are controlled via `ALLOWED_TRANSITIONS` dictionary and `handle_transition()` method.

3. **borrower_company Field**: New field allows direct Company reference for customer tracking, separate from Owner-based borrower.

4. **Stock Validation**: Allocations check `unallocated_quantity()` which includes build, sales, AND loan allocations.

5. **loan_allocation_count()**: Added to StockItem model and included in `allocation_count()`.

6. **Conversion Options**: Can convert to new SalesOrder or add to existing one via `existing_sales_order` parameter.

7. **Permissions**: Any user with `loan_order.add` can create loans. Only superusers can approve.

---

**This proposal requires approval before implementation.**

---

*Document Version: 2.0 - All P0/P1/P2 corrections applied*
*Created: 2025-01-15*
*Last Updated: 2025-02-05*
*Status: Proposal - All Critical Issues Resolved - Ready for Implementation*
