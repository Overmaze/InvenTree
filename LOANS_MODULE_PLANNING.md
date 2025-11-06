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
- Overdue item management
- Historical loan records

### 1.2 Key Features
- Create and manage loan requests
- Approve/reject loan requests
- Track loaned stock items
- Automatic overdue detection and notifications
- Return processing with condition tracking
- Integration with stock management
- Loan history and reporting

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
   - Links borrower (Company/User) to stock items
   - Tracks loan status, dates, responsible person
   - Similar to PurchaseOrder/SalesOrder structure

2. **LoanOrderLineItem** - Individual items in a loan
   - Links to StockItem
   - Tracks quantity, condition, return status
   - Similar to OrderLineItem

3. **LoanOrderTracking** - History/audit trail
   - Tracks status changes, events
   - Similar to StockItemTracking

### 3.2 Business Rules

- Loans can be created by authorized users
- Loans require approval (configurable)
- Stock items must be available (not allocated)
- Due dates are required
- Returns can be partial
- Condition tracking on return (optional)
- Overdue loans trigger notifications
- Stock items are marked as "on loan" during loan period

### 3.3 User Stories

1. As a user, I want to create a loan request for stock items
2. As a manager, I want to approve/reject loan requests
3. As a user, I want to see all my active loans
4. As an admin, I want to see overdue loans
5. As a user, I want to return loaned items
6. As a system, I want to notify about overdue loans
7. As a user, I want to see loan history

---

## 4. Database Models

### 4.1 LoanOrder Model

**File**: `src/backend/InvenTree/loan/models.py`

```python
class LoanOrder(
    StatusCodeMixin,
    StateTransitionMixin,
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
    
    # Reference pattern setting (required for ReferenceIndexingMixin)
    REFERENCE_PATTERN_SETTING = 'LOAN_ORDER_REFERENCE_PATTERN'
    
    # Reference number (auto-generated)
    reference = models.CharField(
        max_length=64,
        unique=True,
        help_text=_('Loan order reference'),
        verbose_name=_('Reference'),
    )
    
    @classmethod
    def validate_reference_field(cls, reference):
        """Validate the reference field matches the required pattern."""
        pattern = cls.get_reference_pattern()
        
        if not pattern:
            # No pattern defined, accept any reference
            return
        
        # Validate pattern (implementation similar to Order.validate_reference_field)
        # Check if reference matches the pattern
        # This is a simplified version - actual implementation would use regex
        pass
    
    # Borrower - can be Company or User (via Owner)
    borrower = models.ForeignKey(
        'users.Owner',
        on_delete=models.PROTECT,
        related_name='loan_orders',
        help_text=_('Borrower (company or user)'),
        verbose_name=_('Borrower'),
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
    
    def is_overdue(self):
        """Check if this loan is overdue."""
        if not self.due_date:
            return False
        if self.status in LoanOrderStatusGroups.COMPLETE:
            return False
        return self.due_date < timezone.now().date()
    
    def overdue_filter():
        """Return Q filter for overdue loans."""
        today = timezone.now().date()
        return Q(
            due_date__lt=today,
            status__in=LoanOrderStatusGroups.OPEN
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
    
    Links a stock item to a loan order with quantity and status.
    """
    
    # Link to loan order
    order = models.ForeignKey(
        'loan.LoanOrder',
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name=_('Loan Order'),
    )
    
    # Stock item being loaned
    item = models.ForeignKey(
        'stock.StockItem',
        on_delete=models.PROTECT,
        related_name='loan_lines',
        verbose_name=_('Stock Item'),
        help_text=_('Stock item being loaned'),
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
    
    # Status
    status = InvenTreeCustomStatusModelField(
        default=LoanOrderLineStatus.PENDING.value,
        verbose_name=_('Status'),
    )
    
    STATUS_CLASS = LoanOrderLineStatus
    
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
        unique_together = [('order', 'item')]
    
    def get_absolute_url(self):
        """Return the absolute URL for this line item."""
        return reverse('loan-line-detail', kwargs={'pk': self.pk})
    
    def is_complete(self):
        """Check if this line item is complete."""
        return self.returned_quantity >= self.loaned_quantity
    
    def is_overdue(self):
        """Check if this line item is overdue."""
        if not self.target_date:
            return False
        if self.status in LoanOrderLineStatusGroups.COMPLETE:
            return False
        return self.target_date < timezone.now().date()
```

### 4.3 LoanOrderTracking Model

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
        choices=LoanTrackingCode.choices,
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

### 4.4 LoanOrderAllocation Model

See Section 12.1 for complete definition of `LoanOrderAllocation` model.

### 4.5 Loan Tracking Codes

**File**: `src/backend/InvenTree/loan/status_codes.py`

```python
class LoanTrackingCode(IntEnum):
    """Tracking codes for loan order history."""
    
    CREATED = 10
    APPROVED = 20
    ISSUED = 30
    ITEM_LOANED = 40
    ITEM_RETURNED = 50
    COMPLETE = 60
    CANCELLED = 70
    OVERDUE = 80
    STATUS_CHANGE = 90
```

### 4.6 Model Relationships

```
LoanOrder (1) ──< (N) LoanOrderLineItem
    │
    ├──> (1) Owner (borrower)
    ├──> (1) Owner (responsible)
    ├──> (1) Contact (optional)
    ├──> (1) Address (optional)
    ├──> (1) ProjectCode (optional)
    ├──> (N) LoanOrderTracking
    └──> (N) LoanOrderLineItem ──< (N) LoanOrderAllocation ──> (1) StockItem

LoanOrderLineItem
    ├──> (1) StockItem (via allocations)
    └──> (N) LoanOrderAllocation
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
                    path(
                        'complete/',
                        LoanOrderComplete.as_view(),
                        name='api-loan-order-complete',
                    ),
                    path(
                        'cancel/',
                        LoanOrderCancel.as_view(),
                        name='api-loan-order-cancel',
                    ),
                    path(
                        'issue/',
                        LoanOrderIssue.as_view(),
                        name='api-loan-order-issue',
                    ),
                    path(
                        'metadata/',
                        MetadataView.as_view(model=LoanOrder),
                        name='api-loan-order-metadata',
                    ),
                    path('', LoanOrderDetail.as_view(), name='api-loan-order-detail'),
                ]),
            ),
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
                    path(
                        'return/',
                        LoanLineReturn.as_view(),
                        name='api-loan-line-return',
                    ),
                    path('', LoanLineDetail.as_view(), name='api-loan-line-detail'),
                ]),
            ),
            path('', LoanLineList.as_view(), name='api-loan-line-list'),
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
    OutputOptionsMixin,
    ListCreateAPI,
):
    """List and create API endpoint for LoanOrder model."""
    
    queryset = LoanOrder.objects.all()
    serializer_class = LoanOrderSerializer
    filterset_class = LoanOrderFilter
    
    role_required = 'loan.view'
    
    filter_backends = SEARCH_ORDER_FILTER
    
    search_fields = [
        'reference',
        'description',
        'borrower__name',
        'contact__name',
    ]
    
    ordering_fields = [
        'reference',
        'creation_date',
        'due_date',
        'status',
    ]
    
    ordering = ['-creation_date']
```

#### LoanOrderDetail
```python
class LoanOrderDetail(
    SerializerContextMixin,
    RetrieveUpdateDestroyAPI,
):
    """Detail API endpoint for LoanOrder model."""
    
    queryset = LoanOrder.objects.all()
    serializer_class = LoanOrderSerializer
    
    role_required = 'loan.view'
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.request.method == 'PATCH':
            return LoanOrderUpdateSerializer
        return LoanOrderSerializer
```

#### LoanOrderIssue
```python
class LoanOrderIssue(
    SerializerContextMixin,
    CreateAPI,
):
    """Issue a loan order (approve and assign stock)."""
    
    queryset = LoanOrder.objects.all()
    serializer_class = LoanOrderIssueSerializer
    
    role_required = 'loan.change'
    
    def create(self, request, *args, **kwargs):
        """Issue the loan order."""
        order = self.get_object()
        
        serializer = self.get_serializer(order, data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Issue the order
        order.issue_loan(request.user)
        
        return Response(
            LoanOrderSerializer(order).data,
            status=status.HTTP_200_OK
        )
```

### 5.3 Serializers

**File**: `src/backend/InvenTree/loan/serializers.py`

```python
class LoanOrderSerializer(
    DataImportExportSerializerMixin,
    FilterableSerializerMixin,
    InvenTreeCustomStatusSerializerMixin,
    InvenTree.serializers.NotesFieldMixin,
    InvenTree.serializers.InvenTreeModelSerializer,
):
    """Serializer for LoanOrder model."""
    
    class Meta:
        model = LoanOrder
        fields = [
            'pk',
            'reference',
            'borrower',
            'borrower_detail',
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
    contact_detail = ContactSerializer(source='contact', read_only=True)
    address_detail = AddressBriefSerializer(source='address', read_only=True)
    responsible_detail = OwnerSerializer(source='responsible', read_only=True)
    created_by_detail = UserSerializer(source='created_by', read_only=True)
    issued_by_detail = UserSerializer(source='issued_by', read_only=True)
    received_by_detail = UserSerializer(source='received_by', read_only=True)
    project_code_detail = ProjectCodeSerializer(source='project_code', read_only=True)
    
    line_items = serializers.IntegerField(read_only=True)
    loaned_items = serializers.IntegerField(read_only=True)
    returned_items = serializers.IntegerField(read_only=True)
    overdue = serializers.BooleanField(read_only=True)
```

---

## 6. Frontend Components

### 6.1 Pages

#### LoansIndex.tsx
**File**: `src/frontend/src/pages/loans/LoansIndex.tsx`

```typescript
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
export default function LoanOrderDetail() {
  const { id } = useParams();
  
  const { instance: loanOrder, instanceQuery } = useInstance({
    endpoint: ApiEndpoints.loan_order_list,
    pk: id
  });
  
  const panels: PanelType[] = useMemo(() => [
    {
      name: 'details',
      label: t`Loan Details`,
      icon: <IconInfoCircle />,
      content: <LoanOrderDetailsPanel order={loanOrder} />
    },
    {
      name: 'lines',
      label: t`Line Items`,
      icon: <IconList />,
      content: <LoanOrderLineItemTable orderId={id} />
    },
    {
      name: 'tracking',
      label: t`Tracking`,
      icon: <IconHistory />,
      content: <LoanOrderTrackingTable orderId={id} />
    },
    {
      name: 'attachments',
      label: t`Attachments`,
      icon: <IconPaperclip />,
      content: <AttachmentTable modelType={ModelType.loanorder} id={id} />
    }
  ], [loanOrder, id]);
  
  return (
    <InstanceDetail query={instanceQuery}>
      <PageDetail
        title={`${t`Loan`}: ${loanOrder.reference}`}
        breadcrumbs={[
          { name: t`Loans`, url: '/loans/' }
        ]}
        actions={<LoanOrderActions order={loanOrder} />}
      />
      <PanelGroup
        pageKey="loan-order"
        panels={panels}
        model={ModelType.loanorder}
        id={id}
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
export function LoanOrderTable(props: Readonly<TableProps>) {
  const table = useTable('loan-order');
  
  const columns: useTableColumn<LoanOrder>[] = useMemo(() => [
    {
      accessor: 'reference',
      title: t`Reference`,
      sortable: true,
      render: (record) => (
        <Link to={`/loans/order/${record.pk}/`}>
          {record.reference}
        </Link>
      )
    },
    {
      accessor: 'borrower_detail.name',
      title: t`Borrower`,
      sortable: true
    },
    {
      accessor: 'status',
      title: t`Status`,
      render: (record) => (
        <StatusRenderer status={record.status} type={ModelType.loanorder} />
      )
    },
    {
      accessor: 'due_date',
      title: t`Due Date`,
      sortable: true,
      render: (record) => (
        <DateRenderer value={record.due_date} />
      )
    },
    {
      accessor: 'overdue',
      title: t`Overdue`,
      render: (record) => (
        record.overdue ? <Badge color="red">{t`Overdue`}</Badge> : null
      )
    }
  ], []);
  
  return (
    <InvenTreeTable
      url={ApiEndpoints.loan_order_list}
      tableState={table.tableState}
      columns={columns}
      props={props}
    />
  );
}
```

### 6.3 Forms

**File**: `src/frontend/src/forms/LoanForms.tsx`

```typescript
export const loanOrderFields: ApiFormFieldSet = {
  reference: {
    type: 'string',
    required: true,
    disabled: true, // Auto-generated
    label: t`Reference`
  },
  borrower: {
    type: 'related_field',
    required: true,
    label: t`Borrower`,
    model_field: 'borrower',
    api_query: {
      endpoint: ApiEndpoints.owner_list
    }
  },
  description: {
    type: 'string',
    required: true,
    label: t`Description`
  },
  due_date: {
    type: 'date',
    required: true,
    label: t`Due Date`
  },
  responsible: {
    type: 'related_field',
    required: false,
    label: t`Responsible`,
    model_field: 'responsible',
    api_query: {
      endpoint: ApiEndpoints.owner_list
    }
  }
};
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
            'stock_stockitem',  # Needed for loaning items
            'users_owner',      # Needed for borrower field
        ],
    }
    return ruleset_models
```

### 7.2 Permission Checks

- `loan_order.view` - View loan orders
- `loan_order.add` - Create loan orders
- `loan_order.change` - Modify loan orders
- `loan_order.delete` - Delete loan orders

### 7.3 API Permission Classes

All API views use `RolePermission`:
```python
class LoanOrderList(..., ListCreateAPI):
    role_required = 'loan_order.view'  # For GET
    # Automatically uses 'loan_order.add' for POST
```

---

## 8. Status Codes & State Transitions

### 8.1 Status Codes

**File**: `src/backend/InvenTree/loan/status_codes.py`

```python
class LoanOrderStatus(StatusCode):
    """Status codes for LoanOrder."""
    
    PENDING = 10, _('Pending'), ColorEnum.info
    APPROVED = 20, _('Approved'), ColorEnum.success
    ISSUED = 30, _('Issued'), ColorEnum.success
    PARTIAL_RETURN = 40, _('Partially Returned'), ColorEnum.warning
    COMPLETE = 50, _('Complete'), ColorEnum.success
    CANCELLED = 60, _('Cancelled'), ColorEnum.danger
    OVERDUE = 70, _('Overdue'), ColorEnum.danger


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
    CANCELLED = 60, _('Cancelled'), ColorEnum.danger


class LoanOrderLineStatusGroups:
    """Groups for LoanOrderLineStatus codes."""
    
    PENDING = [LoanOrderLineStatus.PENDING.value]
    
    ACTIVE = [
        LoanOrderLineStatus.ALLOCATED.value,
        LoanOrderLineStatus.LOANED.value,
    ]
    
    COMPLETE = [LoanOrderLineStatus.RETURNED.value]
```

### 8.2 State Transitions

**File**: `src/backend/InvenTree/loan/models.py`

```python
class LoanOrder(..., StateTransitionMixin, ...):
    
    @TransitionMethod(
        source=[LoanOrderStatus.PENDING],
        target=LoanOrderStatus.APPROVED,
        method_name='approve',
    )
    def approve(self, user=None):
        """Approve the loan order."""
        self.set_status(LoanOrderStatus.APPROVED)
        self.save()
        
        # Create tracking entry
        LoanOrderTracking.objects.create(
            order=self,
            tracking_type=LoanTrackingCode.APPROVED,
            user=user,
            notes=_('Loan order approved'),
        )
    
    @TransitionMethod(
        source=[LoanOrderStatus.PENDING, LoanOrderStatus.APPROVED],
        target=LoanOrderStatus.ISSUED,
        method_name='issue',
    )
    def issue_loan(self, user=None):
        """Issue the loan (assign stock items)."""
        # Allocate stock items
        for line in self.lines.all():
            line.allocate_stock(user=user)
        
        self.issue_date = timezone.now().date()
        self.issued_by = user
        self.set_status(LoanOrderStatus.ISSUED)
        self.save()
        
        # Create tracking entry
        LoanOrderTracking.objects.create(
            order=self,
            tracking_type=LoanTrackingCode.ISSUED,
            user=user,
            notes=_('Loan order issued'),
        )
    
    @TransitionMethod(
        source=[LoanOrderStatus.ISSUED, LoanOrderStatus.PARTIAL_RETURN],
        target=LoanOrderStatus.COMPLETE,
        method_name='complete',
    )
    def complete_loan(self, user=None):
        """Mark loan as complete (all items returned)."""
        # Check all lines are returned
        for line in self.lines.all():
            if not line.is_complete():
                raise ValidationError(_('Not all items have been returned'))
        
        self.return_date = timezone.now().date()
        self.received_by = user
        self.set_status(LoanOrderStatus.COMPLETE)
        self.save()
        
        # Create tracking entry
        LoanOrderTracking.objects.create(
            order=self,
            tracking_type=LoanTrackingCode.COMPLETE,
            user=user,
            notes=_('Loan order completed'),
        )
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
    """Check for overdue loans and send notifications."""
    yesterday = datetime.now().date() - timedelta(days=1)
    
    overdue_loans = LoanOrder.objects.filter(
        due_date=yesterday,
        status__in=LoanOrderStatusGroups.OPEN,
    )
    
    for loan in overdue_loans:
        notify_overdue_loan(loan)


def notify_overdue_loan(loan: LoanOrder):
    """Notify users about an overdue loan."""
    targets: list[User | Group | Owner] = []
    
    if loan.created_by:
        targets.append(loan.created_by)
    
    if loan.responsible:
        targets.append(loan.responsible)
    
    if loan.borrower:
        # Add borrower if it's a user
        if hasattr(loan.borrower, 'user'):
            targets.append(loan.borrower.user)
    
    targets.extend(loan.subscribed_users())
    
    context = {
        'loan': loan,
        'name': _('Overdue Loan'),
        'message': _(f'Loan {loan.reference} is now overdue'),
        'link': construct_absolute_url(loan.get_absolute_url()),
        'template': {
            'html': 'email/overdue_loan.html',
            'subject': _('Overdue Loan'),
        },
    }
    
    common.notifications.trigger_notification(
        loan,
        LoanOrderEvents.OVERDUE,
        targets=targets,
        context=context,
    )
    
    trigger_event(LoanOrderEvents.OVERDUE, loan_order=loan.pk)
```

---

## 10. Background Tasks

### 10.1 Scheduled Tasks

**File**: `src/backend/InvenTree/loan/tasks.py`

```python
@scheduled_task(ScheduledTask.DAILY)
def check_overdue_loans():
    """Check for overdue loans daily."""
    # Implementation above

@scheduled_task(ScheduledTask.DAILY)
def update_loan_statuses():
    """Update loan statuses based on return dates."""
    # Check for loans that should be marked overdue
    today = timezone.now().date()
    
    overdue_loans = LoanOrder.objects.filter(
        due_date__lt=today,
        status__in=LoanOrderStatusGroups.OPEN,
    )
    
    for loan in overdue_loans:
        if loan.status != LoanOrderStatus.OVERDUE:
            loan.set_status(LoanOrderStatus.OVERDUE)
            loan.save()
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
        
        # Create test stock items
        self.stock_item = StockItem.objects.create(
            part=Part.objects.first(),
            location=StockLocation.objects.first(),
            quantity=10,
        )
        
        # Create test borrower
        self.borrower = Owner.objects.create(
            name='Test Borrower',
            user=self.user,
        )


class LoanOrderAPITest(LoanOrderTest):
    """Tests for LoanOrder API."""
    
    LIST_URL = reverse('api-loan-order-list')
    
    def test_create_loan_order(self):
        """Test creating a loan order."""
        data = {
            'borrower': self.borrower.pk,
            'description': 'Test loan',
            'due_date': '2025-12-31',
            'lines': [
                {
                    'item': self.stock_item.pk,
                    'quantity': 5,
                }
            ],
        }
        
        response = self.post(self.LIST_URL, data, expected_code=201)
        
        self.assertEqual(response.data['description'], 'Test loan')
        self.assertEqual(len(response.data['lines']), 1)
    
    def test_issue_loan(self):
        """Test issuing a loan."""
        loan = LoanOrder.objects.create(
            reference='LOAN-001',
            borrower=self.borrower,
            description='Test loan',
            due_date='2025-12-31',
            created_by=self.user,
        )
        
        LoanOrderLineItem.objects.create(
            order=loan,
            item=self.stock_item,
            quantity=5,
        )
        
        url = reverse('api-loan-order-issue', kwargs={'pk': loan.pk})
        response = self.post(url, {}, expected_code=200)
        
        loan.refresh_from_db()
        self.assertEqual(loan.status, LoanOrderStatus.ISSUED.value)
    
    def test_overdue_filter(self):
        """Test overdue loan filtering."""
        yesterday = timezone.now().date() - timedelta(days=1)
        
        overdue_loan = LoanOrder.objects.create(
            reference='LOAN-OVERDUE',
            borrower=self.borrower,
            description='Overdue loan',
            due_date=yesterday,
            status=LoanOrderStatus.ISSUED.value,
            created_by=self.user,
        )
        
        response = self.get(self.LIST_URL, {'overdue': True})
        
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['reference'], 'LOAN-OVERDUE')
```

---

## 12. Integration Points

### 12.1 Stock Item Integration

When a loan is issued:
- Stock items are allocated (similar to sales orders)
- Stock items show as "on loan" status
- Stock quantity remains but is marked as unavailable

**Stock Allocation Model** (similar to SalesOrderAllocation):

**File**: `src/backend/InvenTree/loan/models.py`

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
    
    def clean(self):
        """Validate the allocation."""
        super().clean()
        
        errors = {}
        
        # Check part matches
        if self.line.item.part != self.item.part:
            errors['item'] = _('Part mismatch')
        
        # Check quantity
        if self.quantity > self.item.quantity:
            errors['quantity'] = _('Allocation quantity exceeds stock quantity')
        
        # Check availability (not already allocated to builds, sales, or other loans)
        build_allocation = self.item.build_allocation_count()
        sales_allocation = self.item.sales_order_allocation_count()
        loan_allocation = self.item.loan_allocation_count(exclude_allocations={'pk': self.pk})
        
        total_allocation = build_allocation + sales_allocation + loan_allocation + self.quantity
        
        if total_allocation > self.item.quantity:
            errors['quantity'] = _('Stock item is over-allocated')
        
        if errors:
            raise ValidationError(errors)
    
    def complete_allocation(self, user=None):
        """Complete the allocation (mark as loaned out)."""
        # Update stock item tracking
        # Note: LOANED_OUT must be added to StockHistoryCode in stock/status_codes.py
        self.item.add_tracking_entry(
            StockHistoryCode.LOANED_OUT,
            user,
            {
                'loan_order': self.line.order.pk,
                'loan_order_reference': self.line.order.reference,
            },
            notes=_('Item loaned out'),
        )
        
        # Update line item
        self.line.loaned_quantity += self.quantity
        self.line.set_status(LoanOrderLineStatus.LOANED)
        self.line.save()
    
    def return_allocation(self, quantity, user=None, condition=None):
        """Return allocated stock item."""
        if quantity > self.quantity:
            raise ValidationError(_('Cannot return more than allocated'))
        
        # Update stock item tracking
        # Note: RETURNED_FROM_LOAN must be added to StockHistoryCode in stock/status_codes.py
        self.item.add_tracking_entry(
            StockHistoryCode.RETURNED_FROM_LOAN,
            user,
            {
                'loan_order': self.line.order.pk,
                'loan_order_reference': self.line.order.reference,
                'returned_quantity': str(quantity),
            },
            notes=_('Item returned from loan'),
        )
        
        # Update line item
        self.line.returned_quantity += quantity
        if self.line.returned_quantity >= self.line.loaned_quantity:
            self.line.set_status(LoanOrderLineStatus.RETURNED)
        self.line.save()
        
        # If fully returned, delete allocation
        if quantity >= self.quantity:
            self.delete()
        else:
            self.quantity -= quantity
            self.save()
```

**Extension to StockItem Model**:

Add method to `stock/models.py`:

```python
class StockItem(...):
    
    def loan_allocation_count(self, exclude_allocations=None):
        """Return the total quantity allocated to loan orders."""
        from loan.models import LoanOrderAllocation
        
        allocations = LoanOrderAllocation.objects.filter(item=self)
        
        if exclude_allocations:
            allocations = allocations.exclude(**exclude_allocations)
        
        total = allocations.aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        return total
```

**LoanOrderLineItem Methods**:

```python
class LoanOrderLineItem(...):
    
    def allocate_stock(self, user=None):
        """Allocate stock item for loan."""
        # Check availability
        available = self.item.quantity - (
            self.item.build_allocation_count() +
            self.item.sales_order_allocation_count() +
            self.item.loan_allocation_count()
        )
        
        if available < self.quantity:
            raise ValidationError(_('Insufficient stock available'))
        
        # Create allocation
        allocation = LoanOrderAllocation.objects.create(
            line=self,
            item=self.item,
            quantity=self.quantity,
        )
        
        # Complete allocation (mark as loaned)
        allocation.complete_allocation(user=user)
        
        # Create tracking entry
        LoanOrderTracking.objects.create(
            order=self.order,
            tracking_type=LoanTrackingCode.ITEM_LOANED,
            user=user,
            notes=_('Item {item} loaned (quantity: {qty})').format(
                item=self.item,
                qty=self.quantity,
            ),
        )
    
    def return_stock(self, quantity, user=None, condition=None):
        """Return stock item from loan."""
        allocations = self.allocations.all()
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
            self.set_status(LoanOrderLineStatus.RETURNED)
            self.save()
        
        # Check if all lines are complete
        if self.order.lines.exclude(status=LoanOrderLineStatus.RETURNED).count() == 0:
            self.order.set_status(LoanOrderStatus.COMPLETE)
            self.order.save()
        elif self.returned_quantity > 0:
            self.order.set_status(LoanOrderStatus.PARTIAL_RETURN)
            self.order.save()
```

### 12.2 Company Integration

- Borrowers can be Companies (via Owner model)
- Contact information from Company model
- Address information from Address model

### 12.3 Report Integration

**File**: `src/backend/InvenTree/loan/models.py`

```python
class LoanOrderReportContext(report.mixins.BaseReportContext):
    """Report context for LoanOrder model."""
    
    loan_order: LoanOrder
    borrower: Company
    lines: QuerySet[LoanOrderLineItem]
    tracking: QuerySet[LoanOrderTracking]


class LoanOrder(..., report.mixins.InvenTreeReportMixin, ...):
    
    def report_context(self) -> LoanOrderReportContext:
        """Return report context for loan order."""
        return {
            'loan_order': self,
            'borrower': self.borrower,
            'lines': self.lines.all(),
            'tracking': self.tracking.all(),
        }
```

---

## 13. Implementation Checklist

### 13.1 Backend Implementation

#### Phase 1: Core Models
- [ ] Create `loan/` app directory structure
- [ ] Create `loan/apps.py` with `LoanConfig` class
- [ ] Create `LoanOrder` model with:
  - [ ] `REFERENCE_PATTERN_SETTING = 'LOAN_ORDER_REFERENCE_PATTERN'`
  - [ ] `validate_reference_field()` classmethod
  - [ ] All required mixins and fields
- [ ] Create `LoanOrderLineItem` model
- [ ] Create `LoanOrderTracking` model
- [ ] Create `LoanOrderAllocation` model (see Section 12.1)
- [ ] Define status codes (`status_codes.py`)
- [ ] Define tracking codes (`status_codes.py`)
- [ ] Create `loan/validators.py` with:
  - [ ] `generate_next_loan_order_reference()`
  - [ ] `validate_loan_order_reference_pattern()`
  - [ ] `validate_loan_order_reference()`
- [ ] Add `loan_allocation_count()` method to `StockItem` model
- [ ] Add `LOANED_OUT` and `RETURNED_FROM_LOAN` to `StockHistoryCode` in `stock/status_codes.py`
- [ ] Create initial migration
- [ ] Add model to admin interface (`admin.py`)
- [ ] Create test fixtures (`fixtures/loan.yaml` in YAML format)

#### Phase 2: API Implementation
- [ ] Create serializers (`serializers.py`)
- [ ] Create API views (`api.py`)
- [ ] Create URL patterns in `loan/api.py`
- [ ] Export URL patterns as `loan_api_urls`
- [ ] Register URLs in main `urls.py`: `path('loan/', include(loan.api.loan_api_urls))`
- [ ] Create filters (`filters.py`) if needed (optional, can use default FilterSet)

#### Phase 3: Business Logic
- [ ] Implement state transitions
- [ ] Implement stock allocation logic
- [ ] Implement return processing
- [ ] Create validators (`validators.py`)

#### Phase 4: Events & Notifications
- [ ] Define events (`events.py`)
- [ ] Create notification handlers
- [ ] Create background tasks (`tasks.py`)

#### Phase 5: Permissions
- [ ] Add `LOAN_ORDER = 'loan_order'` to `RuleSetEnum` in `users/ruleset.py`
- [ ] Add `(RuleSetEnum.LOAN_ORDER, _('Loan Orders'))` to `RULESET_CHOICES`
- [ ] Add loan models to `get_ruleset_models()` dictionary
- [ ] Test permission checks

#### Phase 6: Testing
- [ ] Write model tests (`tests.py`)
- [ ] Write API tests (`test_api.py`)
- [ ] Write integration tests
- [ ] Create test fixtures in YAML format (`fixtures/loan.yaml`)
  - Format: `- model: loan.loanorder` with `pk` and `fields` sections

### 13.2 Frontend Implementation

#### Phase 1: Core Components
- [ ] Create `pages/loans/` directory
- [ ] Create `LoansIndex.tsx`
- [ ] Create `LoanOrderDetail.tsx`
- [ ] Create `tables/loans/` directory
- [ ] Create `LoanOrderTable.tsx`
- [ ] Create `LoanOrderLineItemTable.tsx`
- [ ] Create `LoanOrderTrackingTable.tsx`

#### Phase 2: Forms
- [ ] Create `LoanForms.tsx`
- [ ] Create loan order form
- [ ] Create line item form

#### Phase 3: Routing
- [ ] Add lazy-loaded route components to `router.tsx`:
  ```typescript
  export const LoansIndex = Loadable(lazy(() => import('./pages/loans/LoansIndex')));
  export const LoanOrderDetail = Loadable(lazy(() => import('./pages/loans/LoanOrderDetail')));
  ```
- [ ] Add routes: `/loans/` and `/loans/order/:id/`
- [ ] Add navigation menu items (if needed)

#### Phase 4: API Integration
- [ ] Add API endpoints to `ApiEndpoints.tsx` enum (snake_case format):
  ```typescript
  loan_order_list = 'loan/order/',
  loan_order_detail = 'loan/order/:id/',
  loan_order_issue = 'loan/order/:id/issue/',
  loan_order_complete = 'loan/order/:id/complete/',
  loan_order_cancel = 'loan/order/:id/cancel/',
  loan_line_list = 'loan/line/',
  loan_line_detail = 'loan/line/:id/',
  loan_line_return = 'loan/line/:id/return/',
  loan_tracking_list = 'loan/tracking/',
  loan_tracking_detail = 'loan/tracking/:id/',
  ```
- [ ] Add model types to `ModelType.tsx` enum:
  ```typescript
  loanorder = 'loanorder',
  loanorderlineitem = 'loanorderlineitem',
  loanordertracking = 'loanordertracking',
  ```
- [ ] Create API hooks (if needed)
- [ ] Test API integration

#### Phase 5: UI/UX
- [ ] Add status badges
- [ ] Add overdue indicators
- [ ] Add action buttons
- [ ] Add panels for detail view

### 13.3 Documentation

- [ ] Update API documentation
- [ ] Create user documentation
- [ ] Add code comments
- [ ] Update developer guide

### 13.4 Migration & Deployment

- [ ] Create database migrations
- [ ] Test migration on sample data
- [ ] Update requirements (if needed)
- [ ] Update INSTALLED_APPS in settings
- [ ] Test deployment

---

## 14. Additional Considerations

### 14.1 Custom Status Codes

The module should support custom status codes (similar to orders):
- Custom status codes stored in database
- Custom status keys linked to base status codes
- UI support for custom status display

### 14.2 Barcode Support

- Generate barcodes for loan orders
- Support scanning loan orders
- Link barcodes to loan orders

### 14.3 Metadata Support

- Support custom metadata fields
- Metadata API endpoints
- Metadata in serializers

### 14.4 Attachments

- Support file attachments on loan orders
- Attachment API endpoints
- Attachment UI components

### 14.5 Translation

- Add translation strings
- Use `gettext_lazy` for all user-facing strings
- Add to frontend translation files

### 14.6 Performance

- Optimize database queries (prefetch_related, select_related)
- Add database indexes on frequently queried fields (reference, due_date, status, borrower)
- Cache frequently accessed data

### 14.7 Settings Configuration

**File**: `src/backend/InvenTree/common/settings.py`

Add setting definition for loan order reference pattern:

```python
@settings.register
class LoanOrderReferencePatternSetting(InvenTreeSetting):
    """Setting for loan order reference pattern."""
    
    SETTINGS_KEY = 'LOAN_ORDER_REFERENCE_PATTERN'
    SETTINGS_CATEGORY = 'Loans'
    NAME = _('Loan Order Reference Pattern')
    DESCRIPTION = _('Pattern for generating loan order reference numbers')
    DEFAULT_VALUE = 'LOAN-{ref:04d}'
    VALIDATOR = loan.validators.validate_loan_order_reference_pattern
```

### 14.8 Stock History Codes

**File**: `src/backend/InvenTree/stock/status_codes.py`

Add new codes to `StockHistoryCode`:

```python
class StockHistoryCode(StatusCode):
    # ... existing codes ...
    
    # Loan order codes
    LOANED_OUT = 110, _('Loaned out')
    RETURNED_FROM_LOAN = 115, _('Returned from loan')
```

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
│   └── LoanOrderTrackingTable.tsx
└── forms/
    └── LoanForms.tsx
```

### Files to Modify

**Backend**:
- `src/backend/InvenTree/InvenTree/urls.py` - Add loan API URLs
- `src/backend/InvenTree/InvenTree/settings.py` - Add `'loan.apps.LoanConfig'` to INSTALLED_APPS (after 'order' and before 'part')
- `src/backend/InvenTree/users/ruleset.py` - Add loan ruleset
- `tasks.py` - Add `'loan'` to apps list in `apps()` function
- `src/backend/InvenTree/stock/status_codes.py` - Add `LOANED_OUT` and `RETURNED_FROM_LOAN` to `StockHistoryCode`
- `src/backend/InvenTree/common/settings.py` - Add `LOAN_ORDER_REFERENCE_PATTERN` setting definition

**Frontend**:
- `src/frontend/src/router.tsx` - Add loan routes
- `src/frontend/lib/enums/ApiEndpoints.tsx` - Add loan endpoints (snake_case format)
- `src/frontend/lib/enums/ModelType.tsx` - Add loan model types (string enum values)
- Navigation menu configuration
- `src/frontend/lib/enums/ModelInformation.tsx` - Add loan model information (if needed)

---

## 16. Conclusion

This planning document provides a comprehensive roadmap for implementing the Loans module in InvenTree. The module follows established patterns from existing modules (especially the Order module) while adding loan-specific functionality.

**Key Takeaways**:
1. Follow existing InvenTree patterns and conventions
2. Integrate with existing stock, company, and user systems
3. Implement proper permissions and security
4. Provide comprehensive API and UI
5. Include proper testing and documentation

**Next Steps**:
1. Review and approve this plan
2. Begin Phase 1 implementation (Core Models)
3. Iterate based on feedback
4. Complete implementation phases sequentially

**Estimated Complexity**: Medium-High  
**Estimated Time**: 4-6 weeks for full implementation  
**Dependencies**: Stock, Company, Users modules must be functional

---

---

## 17. Revision Notes

### Version 1.1 - Final Review (2025-01-XX)

**Corrections Applied Based on Project Patterns**:

1. **App Configuration**:
   - ✅ Corrected class name from `LoanOrderConfig` to `LoanConfig`
   - ✅ Added exact INSTALLED_APPS registration pattern
   - ✅ Added `tasks.py` apps() function update requirement

2. **Reference Pattern**:
   - ✅ Added `REFERENCE_PATTERN_SETTING` attribute to LoanOrder model
   - ✅ Added `validate_reference_field()` classmethod requirement
   - ✅ Added settings configuration section (14.7)
   - ✅ Added validators.py requirements

3. **Stock Integration**:
   - ✅ Added requirement to extend `StockHistoryCode` with `LOANED_OUT` and `RETURNED_FROM_LOAN`
   - ✅ Added `loan_allocation_count()` method requirement for StockItem

4. **Fixtures**:
   - ✅ Clarified YAML format requirement (matching existing fixtures)
   - ✅ Added format example: `- model: loan.loanorder`

5. **Frontend**:
   - ✅ Added exact ApiEndpoints enum format (snake_case)
   - ✅ Added exact ModelType enum format (string values)
   - ✅ Added lazy loading pattern for routes

6. **Permissions**:
   - ✅ Added exact RuleSetEnum addition pattern
   - ✅ Added exact RULESET_CHOICES addition pattern
   - ✅ Added get_ruleset_models() update requirement

7. **Checklist Improvements**:
   - ✅ Made checklist more granular and specific
   - ✅ Added code examples where appropriate
   - ✅ Added file modification requirements

---

*Document Version: 1.1*  
*Last Updated: 2025-11-05*  
*Status: Planning Complete - Reviewed and Aligned with Project Patterns - Awaiting Approval*

