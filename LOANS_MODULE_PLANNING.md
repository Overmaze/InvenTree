# Loans Module - Comprehensive Planning Document

## Executive Summary

This document provides a complete planning guide for implementing a new "Loans" module in InvenTree. The loans module will allow tracking of borrowed stock items from inventory, including loan requests, approvals, tracking, returns, and overdue management.

**Status**: Planning Phase - Implementation Not Started
**Module Name**: `loan` (backend), `loans` (frontend)
**Language**: All code, comments, and concepts in English

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [InvenTree Architecture Analysis](#inventree-architecture-analysis)
3. [Loans Module Requirements](#loans-module-requirements)
4. [Database Models](#database-models)
5. [API Endpoints](#api-endpoints)
6. [Frontend Components](#frontend-components)
7. [Permissions & Security](#permissions--security)
8. [Status Codes & State Transitions](#status-codes--state-transitions)
9. [Events & Notifications](#events--notifications)
10. [Background Tasks](#background-tasks)
11. [Testing Strategy](#testing-strategy)
12. [Integration Points](#integration-points)
13. [Implementation Checklist](#implementation-checklist)

---

## 1. Project Overview

### 1.1 Purpose
The Loans module enables organizations to track temporary borrowing of stock items from inventory. This includes:
- Loan requests and approvals
- Tracking borrowed items
- Return processing
- Overdue item management (computed property, not status)
- Historical loan records

### 1.2 Key Features
- Create and manage loan requests
- Approve/reject loan requests
- Track loaned stock items
- Automatic overdue detection and notifications
- Return processing with condition tracking
- Integration with stock management
- Loan history and reporting
- Convert loans to sales orders

---

## 2. InvenTree Architecture Analysis

### 2.1 Backend Structure

**Location**: `src/backend/InvenTree/`

**Key Apps**:
- `order/` - Purchase/Sales/Return orders (similar pattern for loans)
- `stock/` - Stock items and locations
- `part/` - Parts catalog
- `company/` - Companies and contacts
- `users/` - User management and permissions
- `common/` - Shared utilities
- `generic/` - Generic state management

**Module Pattern**:
Each module follows this structure:
```
module_name/
├── __init__.py
├── apps.py              # AppConfig
├── models.py            # Database models
├── serializers.py       # DRF serializers
├── api.py              # API views and URLs
├── admin.py            # Django admin
├── filters.py          # Query filters
├── status_codes.py     # Status code definitions
├── events.py           # Event definitions
├── tasks.py            # Background tasks
├── validators.py       # Custom validators
├── migrations/         # Database migrations
├── fixtures/           # Test fixtures
└── tests.py            # Unit tests
```

### 2.2 Frontend Structure

**Location**: `src/frontend/src/`

**Key Patterns**:
- Pages: `pages/loans/` - Detail and list pages
- Tables: `tables/loans/` - Data table components
- Forms: `forms/LoanForms.tsx` - Form definitions
- Routing: Defined in `router.tsx`
- API: Uses TanStack Query for data fetching

### 2.3 Key Technologies

**Backend**:
- Django 5.x (DRF)
- PostgreSQL/MySQL/SQLite
- Django Q2 for background tasks
- Django Allauth for authentication

**Frontend**:
- React 19+
- TypeScript
- Mantine UI
- TanStack Query
- React Router
- Lingui for i18n

---

## 3. Loans Module Requirements

### 3.1 Core Entities

1. **LoanOrder** - Main loan request/order
   - Links borrower (Owner: User/Group) and optionally Company to stock items
   - Tracks loan status, dates, responsible person
   - Similar to PurchaseOrder/SalesOrder structure

2. **LoanOrderLineItem** - Individual items in a loan
   - Links to Part (not StockItem directly)
   - Tracks quantity, condition, return status
   - Similar to SalesOrderLineItem

3. **LoanOrderAllocation** - Stock allocations
   - Links LineItems to actual StockItems
   - Similar to SalesOrderAllocation

4. **LoanOrderTracking** - History/audit trail
   - Tracks status changes, events
   - Similar to StockItemTracking

### 3.2 Business Rules

- Loans can be created by authorized users
- Loans require approval (superuser only)
- Stock items must be available (not allocated to builds/sales/other loans)
- Due dates are required for overdue tracking
- Returns can be partial
- Condition tracking on return (optional)
- Overdue is a computed property based on due_date (NOT a status)
- Stock items are marked as "on loan" during loan period
- Loans can be converted to sales orders

### 3.3 User Stories

1. As a user, I want to create a loan request for stock items
2. As a superuser, I want to approve/reject loan requests
3. As a user, I want to see all my active loans
4. As an admin, I want to see overdue loans
5. As a user, I want to return loaned items
6. As a system, I want to notify about overdue loans
7. As a user, I want to see loan history
8. As a user, I want to convert a loan to a sales order

---

## 4. Database Models

### 4.1 LoanOrder Model

**File**: `src/backend/InvenTree/loan/models.py`

```python
class LoanOrder(
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
    """Model representing a loan order.

    A loan order tracks the borrowing of stock items from inventory.
    """

    STATUS_CLASS = LoanOrderStatus

    # State machine: allowed status transitions
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

    def get_absolute_url(self):
        """Return the absolute URL for this loan order."""
        return reverse('loan-detail', kwargs={'pk': self.pk})

    def get_api_url(self):
        """Return the API URL for this loan order."""
        return reverse('api-loan-order-detail', kwargs={'pk': self.pk})

    @property
    def is_overdue(self) -> bool:
        """Check if this loan is overdue.

        IMPORTANT: OVERDUE is a computed property, NOT a status value.
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

    @classmethod
    def validate_reference_field(cls, reference):
        """Validate the reference field."""
        # Implementation similar to Order.validate_reference_field
        pass
```

### 4.2 LoanOrderLineItem Model

```python
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

    def get_absolute_url(self):
        """Return the absolute URL for this line item."""
        return reverse('loan-line-detail', kwargs={'pk': self.pk})

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
```

### 4.3 LoanOrderAllocation Model

```python
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

        # CRITICAL: Check quantity against UNALLOCATED quantity
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
```

### 4.4 LoanOrderTracking Model

```python
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
```

### 4.5 LoanOrderLineConversion Model

```python
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

### 4.6 Tracking Codes

**File**: `src/backend/InvenTree/loan/status_codes.py`

```python
from enum import IntEnum

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
    OVERDUE_NOTIFIED = 90  # Notification sent, NOT a status change
    STATUS_CHANGE = 100
    RETURNED_ITEMS_SOLD = 110
```

### 4.7 Model Relationships

```
LoanOrder (1) ──< (N) LoanOrderLineItem
    │
    ├──> (1) Owner (borrower - User or Group only)
    ├──> (1) Company (borrower_company - optional, is_customer=True)
    ├──> (1) Owner (responsible)
    ├──> (1) Contact (optional)
    ├──> (1) Address (optional)
    ├──> (1) ProjectCode (optional)
    ├──> (N) LoanOrderTracking
    └──> (N) LoanOrderLineItem ──< (N) LoanOrderAllocation ──> (1) StockItem

LoanOrderLineItem
    ├──> (1) Part
    ├──> (N) LoanOrderAllocation
    └──> (N) LoanOrderLineConversion ──> (1) SalesOrderLineItem
```

---

## 5. API Endpoints

### 5.1 URL Structure

**File**: `src/backend/InvenTree/loan/api.py`

```python
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

**Registration in main URLs**: `src/backend/InvenTree/InvenTree/urls.py`
```python
apipatterns = [
    # ... existing patterns ...
    path('loan/', include(loan.api.loan_api_urls)),
    # ... rest of patterns ...
]
```

### 5.2 API View Classes

#### LoanOrderList
```python
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
```

#### LoanOrderApprove (Superuser Only)
```python
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
        order.handle_transition(LoanOrderStatus.APPROVED.value, user=request.user)

        LoanOrderTracking.objects.create(
            order=order,
            tracking_type=LoanTrackingCode.APPROVED,
            user=request.user,
            notes=_('Loan order approved'),
        )

        return Response(
            LoanOrderSerializer(order).data,
            status=status.HTTP_200_OK
        )
```

---

## 6. Frontend Components

### 6.1 Pages

#### LoansIndex.tsx
**File**: `src/frontend/src/pages/loans/LoansIndex.tsx`

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

#### LoanOrderDetail.tsx
**File**: `src/frontend/src/pages/loans/LoanOrderDetail.tsx`

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

    // Approve action (only for pending orders, superuser only)
    if (loanOrder?.status === 10) {
      actions.push({
        name: 'approve',
        label: t`Approve`,
        icon: <IconInfoCircle />,
      });
    }

    // Issue action (only for approved orders)
    if (loanOrder?.status === 20) {
      actions.push({
        name: 'issue',
        label: t`Issue`,
        icon: <IconPackage />,
      });
    }

    // Complete action (only for issued/partial return orders)
    if ([30, 40].includes(loanOrder?.status)) {
      actions.push({
        name: 'complete',
        label: t`Complete`,
        icon: <IconInfoCircle />,
      });
    }

    // Cancel action (not for completed/cancelled orders)
    if (![50, 60].includes(loanOrder?.status)) {
      actions.push({
        name: 'cancel',
        label: t`Cancel`,
        icon: <IconAlertTriangle />,
        color: 'red',
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
          <ActionDropdown key="actions" actions={loanOrderActions} />,
        ]}
        badges={[
          loanOrder?.overdue && (
            <Badge key="overdue" color="red">{t`Overdue`}</Badge>
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

### 6.2 Tables

#### LoanOrderTable.tsx
**File**: `src/frontend/src/tables/loans/LoanOrderTable.tsx`

```typescript
import { useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge } from '@mantine/core';
import { t } from '@lingui/macro';

import { InvenTreeTable } from '../InvenTreeTable';
import { useTable } from '../../hooks/UseTable';
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

### 6.3 Forms

**File**: `src/frontend/src/forms/LoanForms.tsx`

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
```

### 6.4 Router Updates

**File**: `src/frontend/src/router.tsx`

```typescript
export const LoansIndex = Loadable(
  lazy(() => import('./pages/loans/LoansIndex'))
);

export const LoanOrderDetail = Loadable(
  lazy(() => import('./pages/loans/LoanOrderDetail'))
);

// In routes:
<Route path="/loans/" element={<LoansIndex />} />
<Route path="/loans/order/:id/" element={<LoanOrderDetail />} />
```

---

## 7. Permissions & Security

### 7.1 Ruleset Definition

**File**: `src/backend/InvenTree/users/ruleset.py`

```python
class RuleSetEnum(StringEnum):
    # ... existing rulesets ...
    LOAN_ORDER = 'loan_order'

RULESET_CHOICES = [
    # ... existing choices ...
    (RuleSetEnum.LOAN_ORDER, _('Loan Orders')),
]

def get_ruleset_models() -> dict:
    ruleset_models = {
        # ... existing models ...
        RuleSetEnum.LOAN_ORDER: [
            'loan_loanorder',
            'loan_loanorderlineitem',
            'loan_loanordertracking',
            'loan_loanorderallocation',
            'loan_loanorderlineconversion',
            'stock_stockitem',
            'users_owner',
        ],
    }
    return ruleset_models
```

### 7.2 Permission Checks

- `loan_order.view` - View loan orders
- `loan_order.add` - Create loan orders
- `loan_order.change` - Modify loan orders
- `loan_order.delete` - Delete loan orders

### 7.3 Special Permissions

- **Approve**: Only superusers can approve loan orders
- **Create**: Any user with `loan_order.add` can create loans

---

## 8. Status Codes & State Transitions

### 8.1 Status Codes

**File**: `src/backend/InvenTree/loan/status_codes.py`

```python
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
    OVERDUE_NOTIFIED = 90  # Notification sent, NOT a status change
    STATUS_CHANGE = 100
    RETURNED_ITEMS_SOLD = 110
```

### 8.2 State Machine Transitions

**File**: `src/backend/InvenTree/loan/models.py`

```python
class LoanOrder(...):

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

    def can_transition_to(self, new_status: int) -> bool:
        """Check if transition to new_status is allowed."""
        current_status = self.status
        allowed = self.ALLOWED_TRANSITIONS.get(current_status, [])
        return new_status in allowed

    def handle_transition(self, new_status: int, user=None):
        """Handle status transition with validation."""
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
```

---

## 9. Events & Notifications

### 9.1 Event Definitions

**File**: `src/backend/InvenTree/loan/events.py`

```python
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

### 9.2 Notification Triggers

**File**: `src/backend/InvenTree/loan/tasks.py`

```python
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

---

## 10. Background Tasks

### 10.1 Scheduled Tasks

**File**: `src/backend/InvenTree/loan/tasks.py`

```python
@scheduled_task(ScheduledTask.DAILY)
def check_overdue_loans():
    """Check for loans that became overdue and send notifications.

    NOTE: OVERDUE is a computed property, not a status.
    This task only sends notifications - it does NOT change status.
    """
    yesterday = timezone.now().date() - timedelta(days=1)

    newly_overdue_loans = LoanOrder.objects.filter(
        due_date=yesterday,
        status__in=LoanOrderStatusGroups.OPEN,
    )

    for loan in newly_overdue_loans:
        notify_overdue_loan(loan)
```

---

## 11. Testing Strategy

### 11.1 Test Structure

**File**: `src/backend/InvenTree/loan/test_api.py`

```python
class LoanOrderTest(InvenTreeAPITestCase):
    """Base class for loan API unit testing."""

    fixtures = [
        'category',
        'part',
        'company',
        'location',
        'stock',
        'users',
    ]

    roles = ['loan_order.change', 'loan_order.view']

    def setUp(self):
        """Setup test data."""
        super().setUp()

        self.stock_item = StockItem.objects.create(
            part=Part.objects.first(),
            location=StockLocation.objects.first(),
            quantity=10,
        )

        self.borrower = Owner.objects.first()


class LoanOrderAPITest(LoanOrderTest):
    """Tests for LoanOrder API."""

    LIST_URL = reverse('api-loan-order-list')

    def test_create_loan_order(self):
        """Test creating a loan order."""
        data = {
            'borrower': self.borrower.pk,
            'description': 'Test loan',
            'due_date': '2025-12-31',
        }

        response = self.post(self.LIST_URL, data, expected_code=201)

        self.assertEqual(response.data['description'], 'Test loan')

    def test_state_machine_transitions(self):
        """Test that state machine enforces valid transitions."""
        loan = LoanOrder.objects.create(
            reference='LOAN-001',
            borrower=self.borrower,
            description='Test loan',
            due_date='2025-12-31',
            created_by=self.user,
        )

        # Valid: PENDING -> APPROVED
        loan.handle_transition(LoanOrderStatus.APPROVED.value, self.user)
        self.assertEqual(loan.status, LoanOrderStatus.APPROVED.value)

        # Invalid: APPROVED -> COMPLETE (must go through ISSUED first)
        with self.assertRaises(ValidationError):
            loan.handle_transition(LoanOrderStatus.COMPLETE.value, self.user)

    def test_overdue_property(self):
        """Test that overdue is a computed property, not a status."""
        yesterday = timezone.now().date() - timedelta(days=1)

        loan = LoanOrder.objects.create(
            reference='LOAN-OVERDUE',
            borrower=self.borrower,
            description='Overdue loan',
            due_date=yesterday,
            status=LoanOrderStatus.ISSUED.value,
            created_by=self.user,
        )

        # Overdue should be computed from due_date, not status
        self.assertTrue(loan.is_overdue)
        self.assertEqual(loan.status, LoanOrderStatus.ISSUED.value)

    def test_allocation_validates_unallocated_quantity(self):
        """Test that allocations check unallocated_quantity, not raw quantity."""
        loan = LoanOrder.objects.create(
            reference='LOAN-ALLOC',
            borrower=self.borrower,
            description='Test allocation',
            due_date='2025-12-31',
            created_by=self.user,
        )

        line = LoanOrderLineItem.objects.create(
            order=loan,
            part=self.stock_item.part,
            quantity=5,
        )

        # Allocation should check unallocated_quantity
        allocation = LoanOrderAllocation(
            line=line,
            item=self.stock_item,
            quantity=self.stock_item.unallocated_quantity() + 1,  # Too much
        )

        with self.assertRaises(ValidationError):
            allocation.full_clean()
```

---

## 12. Integration Points

### 12.1 Stock Item Integration

**Extension to StockItem Model** (`stock/models.py`):

```python
class StockItem(...):

    def loan_allocation_count(self, exclude_allocations=None):
        """Return the total quantity allocated to loan orders."""
        from loan.models import LoanOrderAllocation
        from loan.status_codes import LoanOrderStatusGroups

        allocations = LoanOrderAllocation.objects.filter(
            item=self,
            line__order__status__in=LoanOrderStatusGroups.OPEN
        )

        if exclude_allocations:
            allocations = allocations.exclude(**exclude_allocations)

        total = allocations.aggregate(total=Sum('quantity'))['total'] or Decimal(0)
        return total

    def allocation_count(self):
        """Return the total quantity allocated to builds, sales orders, and loans."""
        return (
            self.build_allocation_count() +
            self.sales_order_allocation_count() +
            self.loan_allocation_count()  # ADD THIS
        )
```

### 12.2 Stock History Codes

**File**: `src/backend/InvenTree/stock/status_codes.py`

```python
class StockHistoryCode(StatusCode):
    # ... existing codes ...

    # Loan order codes
    LOANED_OUT = 110, _('Loaned out')
    RETURNED_FROM_LOAN = 115, _('Returned from loan')
    CONVERTED_FROM_LOAN_TO_SALE = 120, _('Converted from loan to sale')
```

### 12.3 Loan to Sales Conversion

Conversion methods support either creating a NEW SalesOrder or adding to an EXISTING one:

```python
def convert_to_sales_order(self, quantity, user=None, sale_price=None, existing_sales_order=None):
    """Convert loaned items to a sales order.

    Args:
        quantity: Quantity to convert
        user: User performing the conversion
        sale_price: Optional sale price per unit
        existing_sales_order: Optional existing SalesOrder to add line to

    Returns:
        SalesOrder: The sales order (new or existing)
    """
    # If existing_sales_order is provided, add line to it
    # Otherwise, create a new SalesOrder
    ...
```

### 12.4 Critical Fixes Required

**1. Report Templates** - Handle `customer=None`:
- `src/backend/InvenTree/report/templates/report/inventree_sales_order_report.html`
- `src/backend/InvenTree/report/templates/report/inventree_sales_order_shipment_report.html`

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

**2. SalesOrderShipment Validation** - Handle `customer=None`:
```python
if self.order and self.shipment_address:
    if self.order.customer and self.shipment_address.company != self.order.customer:
        raise ValidationError({
            'shipment_address': _('Shipment address must match the customer')
        })
```

---

## 13. Implementation Checklist

### 13.1 Backend Implementation

#### Phase 1: Core Models
- [ ] Create `loan/` app directory structure
- [ ] Create `loan/apps.py` with `LoanConfig` class
- [ ] Create `LoanOrder` model with:
  - [ ] `REFERENCE_PATTERN_SETTING = 'LOAN_ORDER_REFERENCE_PATTERN'`
  - [ ] `ALLOWED_TRANSITIONS` state machine dictionary
  - [ ] `can_transition_to()` and `handle_transition()` methods
  - [ ] `is_overdue` as a property (NOT a status)
  - [ ] `borrower` field (ForeignKey to Owner)
  - [ ] `borrower_company` field (ForeignKey to Company, limit_choices_to={'is_customer': True})
  - [ ] All required mixins including `InvenTreeParameterMixin`
- [ ] Create `LoanOrderLineItem` model with `part` field (not `item`)
- [ ] Create `LoanOrderAllocation` model with `unallocated_quantity()` validation
- [ ] Create `LoanOrderTracking` model
- [ ] Create `LoanOrderLineConversion` model
- [ ] Define status codes (NO OVERDUE status)
- [ ] Define tracking codes with proper `IntEnum` import
- [ ] Create `loan/validators.py`
- [ ] Add `loan_allocation_count()` method to `StockItem` model
- [ ] Update `StockItem.allocation_count()` to include loan allocations
- [ ] Add `LOANED_OUT`, `RETURNED_FROM_LOAN`, `CONVERTED_FROM_LOAN_TO_SALE` to `StockHistoryCode`
- [ ] Create initial migration
- [ ] Add models to admin interface

#### Phase 2: API Implementation
- [ ] Create serializers with `overdue` as read-only computed field
- [ ] Create API views with proper role_required
- [ ] Create URL patterns
- [ ] Register URLs in main `urls.py`
- [ ] Create filters with `overdue` as Q filter (not status filter)

#### Phase 3: Business Logic
- [ ] Implement state machine transitions
- [ ] Implement stock allocation logic with `unallocated_quantity()` check
- [ ] Implement return processing
- [ ] Implement conversion methods with `existing_sales_order` option

#### Phase 4: Events & Notifications
- [ ] Define events
- [ ] Create notification handlers
- [ ] Create background tasks (notification only, no status change for overdue)

#### Phase 5: Permissions
- [ ] Add `LOAN_ORDER = 'loan_order'` to `RuleSetEnum`
- [ ] Add to `RULESET_CHOICES`
- [ ] Add loan models to `get_ruleset_models()`
- [ ] Implement superuser-only approval

### 13.2 Frontend Implementation

#### Phase 1: Core Components
- [ ] Create `pages/loans/` directory
- [ ] Create `LoansIndex.tsx` with full implementation
- [ ] Create `LoanOrderDetail.tsx` with full implementation
- [ ] Create `tables/loans/` directory
- [ ] Create `LoanOrderTable.tsx` with full implementation
- [ ] Create `LoanOrderLineItemTable.tsx` with action buttons
- [ ] Create `LoanOrderAllocationTable.tsx`
- [ ] Create `LoanOrderTrackingTable.tsx`

#### Phase 2: Forms
- [ ] Create `LoanForms.tsx` with all form definitions
- [ ] Include `borrower_company` field
- [ ] Include conversion forms with `existing_sales_order` option

#### Phase 3: Routing & Enums
- [ ] Add lazy-loaded route components to `router.tsx`
- [ ] Add routes: `/loans/` and `/loans/order/:id/`
- [ ] Add API endpoints to `ApiEndpoints.tsx`
- [ ] Add model types to `ModelType.tsx`
- [ ] Add model information to `ModelInformation.tsx`

### 13.3 Required File Modifications

**Backend**:
- [ ] `src/backend/InvenTree/InvenTree/settings.py` - Add `'loan.apps.LoanConfig'`
- [ ] `src/backend/InvenTree/InvenTree/urls.py` - Add loan API URLs
- [ ] `src/backend/InvenTree/users/ruleset.py` - Add loan ruleset
- [ ] `tasks.py` - Add `'loan'` to apps list
- [ ] `src/backend/InvenTree/stock/status_codes.py` - Add loan history codes
- [ ] `src/backend/InvenTree/stock/models.py` - Add `loan_allocation_count()` and update `allocation_count()`
- [ ] `src/backend/InvenTree/common/setting/system.py` - Add reference pattern setting
- [ ] `src/backend/InvenTree/order/models.py` - Handle `customer=None` in SalesOrderShipment.clean()
- [ ] Report templates - Add `{% if customer %}` checks

**Frontend**:
- [ ] `src/frontend/src/router.tsx` - Add loan routes
- [ ] `src/frontend/lib/enums/ApiEndpoints.tsx` - Add loan endpoints
- [ ] `src/frontend/lib/enums/ModelType.tsx` - Add loan model types
- [ ] `src/frontend/lib/enums/ModelInformation.tsx` - Add loan model info

---

## 14. Critical Corrections Applied

### 14.1 OVERDUE is a Property, NOT a Status

**Issue**: OVERDUE was defined as a status value (70).

**Correction Applied**:
- Removed `OVERDUE = 70` from `LoanOrderStatus` enum
- Added `is_overdue` property to `LoanOrder` model
- Added `overdue_filter()` static method for Q-based filtering
- Updated filter to use Q filter instead of status filter
- Background task sends notifications but does NOT change status

### 14.2 State Machine Transitions

**Issue**: No state machine enforcement.

**Correction Applied**:
- Added `ALLOWED_TRANSITIONS` dictionary to `LoanOrder`
- Added `can_transition_to()` method
- Added `handle_transition()` method with validation
- All status changes go through `handle_transition()`

### 14.3 borrower_company Field

**Issue**: Owner can only point to User or Group, not Company.

**Correction Applied**:
- Added `borrower_company` field (ForeignKey to Company)
- Field has `limit_choices_to={'is_customer': True}`
- Used in conversions to avoid creating duplicate Companies

### 14.4 Stock Allocation Validation

**Issue**: Allocations checked raw quantity instead of unallocated_quantity.

**Correction Applied**:
- `LoanOrderAllocation.clean()` now checks `item.unallocated_quantity()`
- Added `loan_allocation_count()` to StockItem
- Updated `allocation_count()` to include loan allocations

### 14.5 Conversion Methods

**Issue**: Each conversion created a new SalesOrder.

**Correction Applied**:
- Added `existing_sales_order` parameter to conversion methods
- Can either create new SalesOrder or add to existing one
- Uses `borrower_company` if available for customer

### 14.6 LoanTrackingCode IntEnum Import

**Issue**: Missing `IntEnum` import.

**Correction Applied**:
- Added `from enum import IntEnum` to status_codes.py
- `LoanTrackingCode` properly inherits from `IntEnum`

### 14.7 LoanOrderLineStatus.PARTIALLY_CONVERTED Value

**Issue**: Value was 55, causing collision potential.

**Correction Applied**:
- Changed from 55 to 45
- Now properly ordered: RETURNED(40), PARTIALLY_CONVERTED(45), CONVERTED_TO_SALE(50)

---

## 15. File Structure Summary

### Backend Files to Create

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

### Frontend Files to Create

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

## 16. Conclusion

This planning document provides a comprehensive roadmap for implementing the Loans module in InvenTree. The module follows established patterns from existing modules (especially the Order module) while adding loan-specific functionality.

**Key Design Decisions**:
1. OVERDUE is a computed property, NOT a status value
2. State machine enforces valid status transitions
3. `borrower_company` field allows direct Company reference
4. Stock allocations validate against `unallocated_quantity()`
5. Conversions can add to existing SalesOrders
6. Superuser-only approval for loans

**Next Steps**:
1. Review and approve this plan
2. Begin Phase 1 implementation (Core Models)
3. Iterate based on feedback
4. Complete implementation phases sequentially

**Estimated Complexity**: Medium-High
**Dependencies**: Stock, Company, Users modules must be functional

---

*Document Version: 2.0 - All P0/P1/P2 corrections applied*
*Last Updated: 2025-02-05*
*Status: Planning Complete - All Critical Issues Resolved - Ready for Implementation*
