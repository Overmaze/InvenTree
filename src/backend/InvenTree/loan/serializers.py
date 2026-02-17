"""JSON serializers for the Loan API."""

from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models, transaction
from django.db.models import BooleanField, Case, DecimalField, ExpressionWrapper, F, Q, Value, When
from django.db.models.functions import Coalesce, Greatest
from django.utils.translation import gettext_lazy as _

from rest_framework import serializers
from rest_framework.serializers import ValidationError
from sql_util.utils import SubqueryCount, SubquerySum

import common.filters
import loan.models
import loan.models as models
import order.models as order_models
import part.filters as part_filters
import part.models as part_models
import stock.models
import stock.serializers
from common.currency import currency_code_default
from company.serializers import (
    AddressBriefSerializer,
    CompanyBriefSerializer,
    ContactSerializer,
)
from generic.states.fields import InvenTreeCustomStatusSerializerMixin
from importer.registry import register_importer
from InvenTree.helpers import current_date, str2bool
from InvenTree.mixins import DataImportExportSerializerMixin
from InvenTree.serializers import (
    FilterableSerializerMixin,
    InvenTreeCurrencySerializer,
    InvenTreeDecimalField,
    InvenTreeModelSerializer,
    InvenTreeMoneySerializer,
    NotesFieldMixin,
    enable_filter,
)
from loan.status_codes import (
    LoanOrderLineStatus,
    LoanOrderLineStatusGroups,
    LoanOrderStatus,
    LoanOrderStatusGroups,
)
from part.serializers import PartBriefSerializer
from stock.status_codes import StockStatus
from users.serializers import OwnerSerializer, UserSerializer


class TotalPriceMixin(serializers.Serializer):
    """Serializer mixin which provides total price fields."""

    total_price = InvenTreeMoneySerializer(allow_null=True, read_only=True)

    order_currency = InvenTreeCurrencySerializer(
        allow_blank=True,
        allow_null=True,
        required=False,
        label=_('Order Currency'),
        help_text=_('Currency for this order (leave blank to use company default)'),
    )


class DuplicateLoanOrderSerializer(serializers.Serializer):
    """Serializer for specifying options when duplicating a loan order."""

    class Meta:
        """Metaclass options."""

        fields = ['order_id', 'copy_lines', 'copy_extra_lines']

    order_id = serializers.IntegerField(
        required=True, label=_('Order ID'), help_text=_('ID of the order to duplicate')
    )

    copy_lines = serializers.BooleanField(
        required=False,
        default=True,
        label=_('Copy Lines'),
        help_text=_('Copy line items from the original order'),
    )

    copy_extra_lines = serializers.BooleanField(
        required=False,
        default=True,
        label=_('Copy Extra Lines'),
        help_text=_('Copy extra line items from the original order'),
    )


class AbstractLoanOrderSerializer(
    DataImportExportSerializerMixin, FilterableSerializerMixin, serializers.Serializer
):
    """Abstract serializer class for loan order types."""

    export_exclude_fields = ['notes', 'duplicate']
    import_exclude_fields = ['notes', 'duplicate']

    # Number of line items in this order
    line_items = serializers.IntegerField(
        read_only=True, allow_null=True, label=_('Line Items')
    )

    # Number of completed line items (annotated field)
    completed_lines = serializers.IntegerField(
        read_only=True, allow_null=True, label=_('Completed Lines')
    )

    # Aggregated quantity totals across all line items
    total_quantity = InvenTreeDecimalField(
        read_only=True, allow_null=True, label=_('Total Quantity')
    )

    total_shipped = InvenTreeDecimalField(
        read_only=True, allow_null=True, label=_('Total Shipped')
    )

    total_returned = InvenTreeDecimalField(
        read_only=True, allow_null=True, label=_('Total Returned')
    )

    # Human-readable status text
    status_text = serializers.CharField(source='get_status_display', read_only=True)

    # Status field cannot be set directly
    status = serializers.IntegerField(read_only=True, label=_('Order Status'))

    # Reference string is required
    reference = serializers.CharField(required=True)

    # Detail for contact field
    contact_detail = enable_filter(
        ContactSerializer(
            source='contact', many=False, read_only=True, allow_null=True
        ),
        True,
        prefetch_fields=['contact'],
    )

    # Detail for responsible field
    responsible_detail = enable_filter(
        OwnerSerializer(
            source='responsible', read_only=True, allow_null=True, many=False
        ),
        True,
        prefetch_fields=['responsible'],
    )

    project_code_label = common.filters.enable_project_label_filter()
    project_code_detail = common.filters.enable_project_code_filter()

    # Detail for address field
    address_detail = enable_filter(
        AddressBriefSerializer(
            source='address', many=False, read_only=True, allow_null=True
        ),
        True,
        prefetch_fields=['address'],
    )

    parameters = common.filters.enable_parameters_filter()

    # Boolean field indicating if this order is overdue (annotated)
    overdue = serializers.BooleanField(read_only=True, allow_null=True)

    barcode_hash = serializers.CharField(read_only=True)

    creation_date = serializers.DateField(
        required=False, allow_null=True, label=_('Creation Date')
    )

    created_by = UserSerializer(read_only=True)

    duplicate = DuplicateLoanOrderSerializer(
        label=_('Duplicate Order'),
        help_text=_('Specify options for duplicating this order'),
        required=False,
        write_only=True,
    )

    def validate_reference(self, reference):
        """Custom validation for the reference field."""
        self.Meta.model.validate_reference_field(reference)
        return reference

    @staticmethod
    def annotate_queryset(queryset):
        """Add extra information to the queryset."""
        queryset = queryset.annotate(line_items=SubqueryCount('lines'))

        # Aggregate shipped/returned totals across all line items
        queryset = queryset.annotate(
            total_quantity=Coalesce(
                SubquerySum('lines__quantity'),
                Decimal(0),
                output_field=DecimalField(),
            ),
            total_shipped=Coalesce(
                SubquerySum('lines__shipped'),
                Decimal(0),
                output_field=DecimalField(),
            ),
            total_returned=Coalesce(
                SubquerySum('lines__returned'),
                Decimal(0),
                output_field=DecimalField(),
            ),
        )

        queryset = queryset.select_related('created_by')
        return queryset

    @staticmethod
    def order_fields(extra_fields):
        """Construct a set of fields for this serializer."""
        return [
            'pk',
            'created_by',
            'creation_date',
            'issue_date',
            'ship_date',
            'due_date',
            'return_date',
            'description',
            'link',
            'project_code',
            'project_code_detail',
            'project_code_label',
            'reference',
            'responsible',
            'responsible_detail',
            'contact',
            'contact_detail',
            'address',
            'address_detail',
            'status',
            'status_text',
            'status_custom_key',
            'notes',
            'overdue',
            'barcode_hash',
            'line_items',
            'completed_lines',
            'total_quantity',
            'total_shipped',
            'total_returned',
            'parameters',
            'duplicate',
            *extra_fields,
        ]


@register_importer()
class LoanOrderSerializer(
    NotesFieldMixin,
    TotalPriceMixin,
    InvenTreeCustomStatusSerializerMixin,
    AbstractLoanOrderSerializer,
    InvenTreeModelSerializer,
):
    """Serializer for the LoanOrder model class."""

    class Meta:
        """Metaclass options."""

        model = loan.models.LoanOrder
        fields = AbstractLoanOrderSerializer.order_fields([
            'borrower_company',
            'borrower_company_detail',
            'converted_sales_order',
            'total_price',
            'order_currency',
        ])
        read_only_fields = ['status', 'creation_date', 'ship_date', 'return_date']
        extra_kwargs = {'order_currency': {'required': False}}

    def skip_create_fields(self):
        """Skip these fields when instantiating a new object."""
        fields = super().skip_create_fields()
        return [*fields, 'duplicate']

    @staticmethod
    def annotate_queryset(queryset):
        """Add extra information to the queryset."""
        queryset = AbstractLoanOrderSerializer.annotate_queryset(queryset)

        # Completed lines (returned or converted)
        queryset = queryset.annotate(
            completed_lines=SubqueryCount(
                'lines',
                filter=Q(status__in=LoanOrderLineStatusGroups.COMPLETE)
            )
        )

        # Overdue annotation (computed from due_date and OPEN status)
        queryset = queryset.annotate(
            overdue=Case(
                When(
                    loan.models.LoanOrder.overdue_filter(),
                    then=Value(True, output_field=BooleanField()),
                ),
                default=Value(False, output_field=BooleanField()),
            )
        )

        return queryset

    borrower_company_detail = enable_filter(
        CompanyBriefSerializer(
            source='borrower_company', many=False, read_only=True, allow_null=True
        ),
        prefetch_fields=['borrower_company'],
    )


class LoanOrderIssueSerializer(serializers.Serializer):
    """Serializer for issuing a LoanOrder."""

    class Meta:
        """Metaclass options."""

        fields = []

    def save(self):
        """Save the serializer to 'issue' the order and return updated order."""
        order = self.context['order']
        order.issue_order()
        order.refresh_from_db()
        return order


class LoanOrderHoldSerializer(serializers.Serializer):
    """Serializer for placing a LoanOrder on hold."""

    class Meta:
        """Metaclass options."""

        fields = []

    def save(self):
        """Save the serializer to place order on hold and return updated order."""
        order = self.context['order']
        order.hold_order()
        order.refresh_from_db()
        return order


class LoanOrderCancelSerializer(serializers.Serializer):
    """Serializer for cancelling a LoanOrder."""

    class Meta:
        """Metaclass options."""

        fields = []

    def save(self):
        """Save the serializer to cancel the order and return updated order."""
        order = self.context['order']
        order.cancel_order()
        order.refresh_from_db()
        return order


class LoanOrderReturnSerializer(serializers.Serializer):
    """Serializer for marking a LoanOrder as returned."""

    class Meta:
        """Metaclass options."""

        fields = []

    def save(self):
        """Save the serializer to mark order as returned and return updated order."""
        order = self.context['order']
        order.return_order()
        order.refresh_from_db()
        return order


class LoanOrderConvertSerializer(serializers.Serializer):
    """Serializer for converting a LoanOrder to a SalesOrder."""

    class Meta:
        """Metaclass options."""

        fields = ['create_sales_order']

    create_sales_order = serializers.BooleanField(
        default=True,
        label=_('Create Sales Order'),
        help_text=_('Automatically create a Sales Order from this loan'),
    )

    def save(self):
        """Save the serializer to convert the order and return updated order."""
        order = self.context['order']
        data = self.validated_data

        order.convert_to_sale()

        # Optionally create a SalesOrder
        if data.get('create_sales_order', True):
            # Create sales order from loan (implementation can be extended)
            pass

        order.refresh_from_db()
        return order


class LoanOrderWriteOffSerializer(serializers.Serializer):
    """Serializer for writing off a LoanOrder."""

    class Meta:
        """Metaclass options."""

        fields = ['reason']

    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        label=_('Reason'),
        help_text=_('Reason for writing off the loan'),
    )

    def save(self):
        """Save the serializer to write off the order and return updated order."""
        order = self.context['order']
        order.write_off_order()
        order.refresh_from_db()
        return order


class AbstractLineItemSerializer(FilterableSerializerMixin, serializers.Serializer):
    """Abstract serializer class for loan line items."""

    quantity = InvenTreeDecimalField()

    @staticmethod
    def line_fields(extra_fields):
        """Construct a set of fields for this serializer."""
        return [
            'pk',
            'quantity',
            'reference',
            'notes',
            'link',
            'order',
            'order_detail',
            'target_date',
            'project_code',
            'project_code_detail',
            'project_code_label',
            *extra_fields,
        ]

    order_detail = enable_filter(
        LoanOrderSerializer(source='order', many=False, read_only=True),
        True,
        prefetch_fields=['order'],
    )

    project_code_label = common.filters.enable_project_label_filter()
    project_code_detail = common.filters.enable_project_code_filter()


@register_importer()
class LoanOrderLineItemSerializer(
    DataImportExportSerializerMixin,
    InvenTreeCustomStatusSerializerMixin,
    AbstractLineItemSerializer,
    InvenTreeModelSerializer,
):
    """Serializer for a LoanOrderLineItem object."""

    class Meta:
        """Metaclass options."""

        model = loan.models.LoanOrderLineItem
        fields = AbstractLineItemSerializer.line_fields([
            'allocated',
            'borrower_company_detail',
            'overdue',
            'part',
            'part_detail',
            'loan_price',
            'loan_price_currency',
            'shipped',
            'returned',
            'status',
            'status_text',
            'status_custom_key',
            # Annotated fields for part stocking information
            'available_stock',
            'on_loan',
        ])

    @staticmethod
    def annotate_queryset(queryset):
        """Add extra annotations to this queryset."""
        queryset = queryset.annotate(
            overdue=Case(
                When(
                    Q(order__status__in=LoanOrderStatusGroups.OPEN)
                    & loan.models.LoanOrderLineItem.OVERDUE_FILTER,
                    then=Value(True, output_field=BooleanField()),
                ),
                default=Value(False, output_field=BooleanField()),
            )
        )

        # Annotate each line with the available stock quantity
        queryset = queryset.alias(
            total_stock=part_filters.annotate_total_stock(reference='part__'),
            allocated_to_sales_orders=part_filters.annotate_sales_order_allocations(
                reference='part__'
            ),
            allocated_to_build_orders=part_filters.annotate_build_order_allocations(
                reference='part__'
            ),
        )

        queryset = queryset.annotate(
            available_stock=Greatest(
                ExpressionWrapper(
                    F('total_stock')
                    - F('allocated_to_sales_orders')
                    - F('allocated_to_build_orders'),
                    output_field=DecimalField(),
                ),
                0,
                output_field=DecimalField(),
            )
        )

        # On loan quantity (shipped - returned)
        queryset = queryset.annotate(
            on_loan=ExpressionWrapper(
                F('shipped') - F('returned'),
                output_field=DecimalField(),
            )
        )

        # Allocated quantity
        queryset = queryset.annotate(
            allocated=Coalesce(
                SubquerySum('allocations__quantity'),
                Decimal(0),
                output_field=DecimalField(),
            )
        )

        return queryset

    part_detail = enable_filter(
        PartBriefSerializer(source='part', many=False, read_only=True),
        True,
        prefetch_fields=['part'],
    )

    # Annotated fields
    allocated = serializers.DecimalField(
        read_only=True, max_digits=15, decimal_places=5, allow_null=True
    )

    on_loan = serializers.DecimalField(
        read_only=True, max_digits=15, decimal_places=5, allow_null=True,
        label=_('On Loan'),
    )

    available_stock = serializers.DecimalField(
        read_only=True, max_digits=15, decimal_places=5, allow_null=True
    )

    overdue = serializers.BooleanField(read_only=True, allow_null=True)

    status_text = serializers.CharField(source='get_status_display', read_only=True)

    # Price fields - must be explicitly declared for Money fields
    loan_price = InvenTreeMoneySerializer(allow_null=True)

    loan_price_currency = InvenTreeCurrencySerializer(
        help_text=_('Loan price currency')
    )

    borrower_company_detail = enable_filter(
        CompanyBriefSerializer(
            source='order__borrower_company', many=False, read_only=True, allow_null=True
        ),
        False,
    )

    def validate_quantity(self, value):
        """Validate quantity is positive."""
        if value is not None and value <= 0:
            raise ValidationError(_('Quantity must be greater than zero'))
        return value

    def validate_part(self, value):
        """Validate part is active and salable."""
        if value:
            if not value.active:
                raise ValidationError(_('Part is not active'))
            if not value.salable:
                raise ValidationError(_('Only salable parts can be added to a loan order'))
        return value

    def validate(self, data):
        """Cross-field validation."""
        data = super().validate(data)

        order = data.get('order', getattr(self.instance, 'order', None))

        # Cannot add/edit line items on completed/cancelled orders
        if order and order.status in (
            LoanOrderStatusGroups.COMPLETE + LoanOrderStatusGroups.FAILED
        ):
            raise ValidationError({
                'order': _('Cannot modify line items for a completed or cancelled order'),
            })

        # Line item target_date cannot exceed the order's due_date
        target_date = data.get('target_date', getattr(self.instance, 'target_date', None))
        if order and target_date and order.due_date:
            if target_date > order.due_date:
                raise ValidationError({
                    'target_date': _('Target date cannot be after the order due date'),
                })

        return data


class LoanOrderAllocationSerializer(InvenTreeModelSerializer):
    """Serializer for the LoanOrderAllocation model."""

    class Meta:
        """Metaclass options."""

        model = loan.models.LoanOrderAllocation
        fields = [
            'pk',
            'line',
            'line_detail',
            'item',
            'item_detail',
            'quantity',
            'returned',
            'location',
            'part',
            'order',
        ]

        read_only_fields = ['pk', 'returned']

    def __init__(self, *args, **kwargs):
        """Initialize the serializer."""
        order_detail = kwargs.pop('order_detail', False)
        item_detail = kwargs.pop('item_detail', False)
        line_detail = kwargs.pop('line_detail', False)
        part_detail = kwargs.pop('part_detail', False)

        super().__init__(*args, **kwargs)

        if not order_detail:
            self.fields.pop('order', None)

        if not item_detail:
            self.fields.pop('item_detail', None)

        if not line_detail:
            self.fields.pop('line_detail', None)

        if not part_detail:
            self.fields.pop('part', None)

    line_detail = LoanOrderLineItemSerializer(source='line', many=False, read_only=True)

    item_detail = stock.serializers.StockItemSerializer(
        source='item', many=False, read_only=True
    )

    quantity = InvenTreeDecimalField()

    location = serializers.IntegerField(
        source='get_location', read_only=True, allow_null=True
    )

    part = serializers.PrimaryKeyRelatedField(
        source='item.part', many=False, read_only=True
    )

    order = serializers.PrimaryKeyRelatedField(
        source='line.order', many=False, read_only=True
    )


class LoanOrderShipItemsSerializer(serializers.Serializer):
    """Serializer for shipping items out on loan."""

    class Meta:
        """Metaclass options."""

        fields = ['items']

    items = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        label=_('Items'),
        help_text=_('List of items to ship'),
    )

    def validate_items(self, items):
        """Validate the items list."""
        if len(items) == 0:
            raise ValidationError(_('At least one item must be specified'))

        for item in items:
            if 'line_item' not in item:
                raise ValidationError(_('Each item must specify a line_item'))
            if 'stock_item' not in item:
                raise ValidationError(_('Each item must specify a stock_item'))
            if 'quantity' not in item:
                raise ValidationError(_('Each item must specify a quantity'))

            # Validate line_item exists
            try:
                line = loan.models.LoanOrderLineItem.objects.get(pk=item['line_item'])
                item['line_item'] = line
            except loan.models.LoanOrderLineItem.DoesNotExist:
                raise ValidationError(_('Invalid line item ID'))

            # Validate stock_item exists
            try:
                stock_item = stock.models.StockItem.objects.get(pk=item['stock_item'])
                item['stock_item'] = stock_item
            except stock.models.StockItem.DoesNotExist:
                raise ValidationError(_('Invalid stock item ID'))

            # Validate quantity
            try:
                quantity = Decimal(str(item['quantity']))
                if quantity <= 0:
                    raise ValidationError(_('Quantity must be greater than zero'))
                item['quantity'] = quantity
            except (ValueError, TypeError):
                raise ValidationError(_('Invalid quantity'))

        return items

    @transaction.atomic
    def save(self):
        """Ship the items."""
        order = self.context['order']
        user = self.context['request'].user
        items = self.validated_data['items']

        return order.ship_line_items(items, user)


class LoanOrderShipAllSerializer(serializers.Serializer):
    """Serializer for auto-allocating and shipping all pending line items."""

    class Meta:
        """Metaclass options."""

        fields = []

    @transaction.atomic
    def save(self):
        """Auto-allocate stock and ship all pending items."""
        order = self.context['order']
        user = self.context['request'].user

        return order.ship_all_line_items(user)


class LoanOrderReturnItemsSerializer(serializers.Serializer):
    """Serializer for returning items from loan."""

    class Meta:
        """Metaclass options."""

        fields = ['items', 'location']

    items = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        label=_('Items'),
        help_text=_('List of items to return'),
    )

    location = serializers.PrimaryKeyRelatedField(
        queryset=stock.models.StockLocation.objects.all(),
        required=False,
        allow_null=True,
        label=_('Location'),
        help_text=_('Default location for returned items'),
    )

    def validate_items(self, items):
        """Validate the items list."""
        if len(items) == 0:
            raise ValidationError(_('At least one item must be specified'))

        for item in items:
            if 'allocation' not in item:
                raise ValidationError(_('Each item must specify an allocation'))
            if 'quantity' not in item:
                raise ValidationError(_('Each item must specify a quantity'))

            # Validate allocation exists
            try:
                allocation = loan.models.LoanOrderAllocation.objects.get(
                    pk=item['allocation']
                )
                item['allocation'] = allocation
            except loan.models.LoanOrderAllocation.DoesNotExist:
                raise ValidationError(_('Invalid allocation ID'))

            # Validate quantity
            try:
                quantity = Decimal(str(item['quantity']))
                if quantity <= 0:
                    raise ValidationError(_('Quantity must be greater than zero'))
                item['quantity'] = quantity
            except (ValueError, TypeError):
                raise ValidationError(_('Invalid quantity'))

            # Optional status
            if 'status' in item:
                try:
                    item['status'] = int(item['status'])
                except (ValueError, TypeError):
                    raise ValidationError(_('Invalid status'))

            # Optional location
            if 'location' in item:
                try:
                    location = stock.models.StockLocation.objects.get(
                        pk=item['location']
                    )
                    item['location'] = location
                except stock.models.StockLocation.DoesNotExist:
                    raise ValidationError(_('Invalid location ID'))

        return items

    @transaction.atomic
    def save(self):
        """Return the items."""
        order = self.context['order']
        user = self.context['request'].user
        items = self.validated_data['items']
        location = self.validated_data.get('location')

        return order.return_line_items(items, user, location=location)


class LoanOrderExtraLineSerializer(InvenTreeModelSerializer):
    """Serializer for LoanOrderExtraLine model."""

    class Meta:
        """Metaclass options."""

        model = loan.models.LoanOrderExtraLine
        fields = [
            'pk',
            'order',
            'order_detail',
            'quantity',
            'reference',
            'description',
            'notes',
            'price',
            'price_currency',
            'link',
        ]

    order_detail = enable_filter(
        LoanOrderSerializer(source='order', many=False, read_only=True),
        False,
    )

    quantity = InvenTreeDecimalField()

    price = InvenTreeMoneySerializer(allow_null=True)
    price_currency = InvenTreeCurrencySerializer()


# Line-level conversion serializers

class LoanOrderLineConvertToSaleSerializer(serializers.Serializer):
    """Serializer for converting loan line items to sales."""

    class Meta:
        """Metaclass options."""

        fields = ['quantity', 'sale_price', 'existing_sales_order', 'notes']

    quantity = serializers.DecimalField(
        max_digits=15,
        decimal_places=5,
        required=True,
        label=_('Quantity'),
        help_text=_('Quantity to convert to sale'),
    )

    sale_price = serializers.DecimalField(
        max_digits=19,
        decimal_places=6,
        required=False,
        allow_null=True,
        label=_('Sale Price'),
        help_text=_('Unit price for the sale'),
    )

    existing_sales_order = serializers.PrimaryKeyRelatedField(
        queryset=order_models.SalesOrder.objects.all(),
        required=False,
        allow_null=True,
        label=_('Existing Sales Order'),
        help_text=_('Add to existing sales order instead of creating new one'),
    )

    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        label=_('Notes'),
        help_text=_('Additional notes about the conversion'),
    )

    def validate_quantity(self, quantity):
        """Validate quantity."""
        line_item = self.context['line_item']
        
        if quantity <= 0:
            raise ValidationError(_('Quantity must be greater than zero'))
            
        if quantity > line_item.available_to_convert:
            raise ValidationError(_(
                f'Cannot convert {quantity}. Only {line_item.available_to_convert} available.'
            ))
            
        return quantity

    def save(self):
        """Convert line items to sale."""
        line_item = self.context['line_item']
        data = self.validated_data
        user = self.context.get('request').user if self.context.get('request') else None

        # Import Money for price handling
        from djmoney.money import Money
        
        sale_price = None
        if data.get('sale_price'):
            # Get currency from existing sales order or default currency
            currency = (
                data.get('existing_sales_order').customer.currency
                if data.get('existing_sales_order')
                else currency_code_default()
            )
            sale_price = Money(data['sale_price'], currency)

        conversion = line_item.convert_to_sales_order(
            quantity=data['quantity'],
            user=user,
            sale_price=sale_price,
            existing_sales_order=data.get('existing_sales_order'),
            notes=data.get('notes', ''),
        )

        return conversion


class LoanOrderLineSellReturnedSerializer(serializers.Serializer):
    """Serializer for selling returned loan items."""

    class Meta:
        """Metaclass options."""

        fields = ['quantity', 'sale_price', 'existing_sales_order', 'notes']

    quantity = serializers.DecimalField(
        max_digits=15,
        decimal_places=5,
        required=True,
        label=_('Quantity'),
        help_text=_('Quantity of returned items to sell'),
    )

    sale_price = serializers.DecimalField(
        max_digits=19,
        decimal_places=6,
        required=False,
        allow_null=True,
        label=_('Sale Price'),
        help_text=_('Unit price for the sale'),
    )

    existing_sales_order = serializers.PrimaryKeyRelatedField(
        queryset=order_models.SalesOrder.objects.all(),
        required=False,
        allow_null=True,
        label=_('Existing Sales Order'),
        help_text=_('Add to existing sales order'),
    )

    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        label=_('Notes'),
        help_text=_('Additional notes'),
    )

    def validate_quantity(self, quantity):
        """Validate quantity."""
        line_item = self.context['line_item']
        
        if quantity <= 0:
            raise ValidationError(_('Quantity must be greater than zero'))
            
        if quantity > line_item.available_returned_to_sell:
            raise ValidationError(_(
                f'Cannot sell {quantity}. Only {line_item.available_returned_to_sell} returned items available.'
            ))
            
        return quantity

    def save(self):
        """Sell returned items."""
        line_item = self.context['line_item']
        data = self.validated_data
        user = self.context.get('request').user if self.context.get('request') else None

        from djmoney.money import Money
        
        sale_price = None
        if data.get('sale_price'):
            sale_price = Money(data['sale_price'], 'USD')

        conversion = line_item.sell_returned_items(
            quantity=data['quantity'],
            user=user,
            sale_price=sale_price,
            existing_sales_order=data.get('existing_sales_order'),
            notes=data.get('notes', ''),
        )

        return conversion


class LoanOrderLineConversionSerializer(serializers.ModelSerializer):
    """Serializer for LoanOrderLineConversion model."""

    class Meta:
        """Metaclass options."""

        model = models.LoanOrderLineConversion
        fields = [
            'pk',
            'loan_line',
            'sales_order_line',
            'quantity',
            'converted_date',
            'converted_by',
            'is_returned_items',
            'conversion_price',
            'notes',
        ]
        read_only_fields = [
            'pk',
            'converted_date',
        ]


class LoanOrderApproveSerializer(serializers.Serializer):
    """Serializer for approving a LoanOrder."""

    class Meta:
        """Metaclass options."""

        fields = ['notes']

    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        label=_('Notes'),
        help_text=_('Approval notes'),
    )

    def save(self):
        """Approve the order and return updated order."""
        order = self.context['order']
        order.approve_order()
        order.refresh_from_db()
        return order


# Batch conversion serializers


class LoanOrderConvertItemsSerializer(serializers.Serializer):
    """Serializer for batch converting multiple loan line items to sales."""

    class Meta:
        """Metaclass options."""

        fields = ['items', 'existing_sales_order', 'notes']

    items = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        label=_('Items'),
        help_text=_('List of line items to convert with quantities and prices'),
    )

    existing_sales_order = serializers.PrimaryKeyRelatedField(
        queryset=order_models.SalesOrder.objects.all(),
        required=False,
        allow_null=True,
        label=_('Existing Sales Order'),
        help_text=_('Add to existing sales order instead of creating new one'),
    )

    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        label=_('Notes'),
        help_text=_('Additional notes for all conversions'),
    )

    def validate_items(self, items):
        """Validate items list."""
        if not items or len(items) == 0:
            raise ValidationError(_('At least one item must be provided'))

        order = self.context['order']

        # Validate each item
        for item_data in items:
            if 'line_item' not in item_data:
                raise ValidationError(_('Each item must have a line_item ID'))
            if 'quantity' not in item_data:
                raise ValidationError(_('Each item must have a quantity'))

            line_item_id = item_data['line_item']
            quantity = Decimal(str(item_data['quantity']))

            # Verify line item belongs to this order
            try:
                line_item = models.LoanOrderLineItem.objects.get(
                    pk=line_item_id, order=order
                )
            except models.LoanOrderLineItem.DoesNotExist:
                raise ValidationError(
                    _(f'Line item {line_item_id} not found in this loan order')
                )

            # Verify quantity is valid
            if quantity <= 0:
                raise ValidationError(
                    _(f'Quantity must be greater than zero for line item {line_item_id}')
                )

            if quantity > line_item.available_to_convert:
                raise ValidationError(
                    _(
                        f'Cannot convert {quantity} from line item {line_item_id}. '
                        f'Only {line_item.available_to_convert} available.'
                    )
                )

        return items

    def save(self):
        """Convert multiple line items to sale."""
        order = self.context['order']
        data = self.validated_data
        user = self.context.get('request').user if self.context.get('request') else None

        from djmoney.money import Money

        conversions = []

        # Process each item
        for item_data in data['items']:
            line_item = models.LoanOrderLineItem.objects.get(
                pk=item_data['line_item'], order=order
            )

            quantity = Decimal(str(item_data['quantity']))

            # Handle sale price
            sale_price = None
            if 'sale_price' in item_data and item_data['sale_price']:
                # Get currency from existing sales order or default currency
                currency = (
                    data.get('existing_sales_order').customer.currency
                    if data.get('existing_sales_order')
                    else currency_code_default()
                )
                sale_price = Money(item_data['sale_price'], currency)

            # Convert
            conversion = line_item.convert_to_sales_order(
                quantity=quantity,
                user=user,
                sale_price=sale_price,
                existing_sales_order=data.get('existing_sales_order'),
                notes=data.get('notes', ''),
            )

            conversions.append(conversion)

        return conversions


class LoanOrderSellReturnedItemsSerializer(serializers.Serializer):
    """Serializer for batch selling multiple returned items."""

    class Meta:
        """Metaclass options."""

        fields = ['items', 'existing_sales_order', 'notes']

    items = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        label=_('Items'),
        help_text=_('List of returned line items to sell with quantities and prices'),
    )

    existing_sales_order = serializers.PrimaryKeyRelatedField(
        queryset=order_models.SalesOrder.objects.all(),
        required=False,
        allow_null=True,
        label=_('Existing Sales Order'),
        help_text=_('Add to existing sales order'),
    )

    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        label=_('Notes'),
        help_text=_('Additional notes'),
    )

    def validate_items(self, items):
        """Validate items list."""
        if not items or len(items) == 0:
            raise ValidationError(_('At least one item must be provided'))

        order = self.context['order']

        for item_data in items:
            if 'line_item' not in item_data:
                raise ValidationError(_('Each item must have a line_item ID'))
            if 'quantity' not in item_data:
                raise ValidationError(_('Each item must have a quantity'))

            line_item_id = item_data['line_item']
            quantity = Decimal(str(item_data['quantity']))

            try:
                line_item = models.LoanOrderLineItem.objects.get(
                    pk=line_item_id, order=order
                )
            except models.LoanOrderLineItem.DoesNotExist:
                raise ValidationError(_(f'Line item {line_item_id} not found'))

            if quantity <= 0:
                raise ValidationError(_(f'Quantity must be greater than zero'))

            if quantity > line_item.available_returned_to_sell:
                raise ValidationError(
                    _(
                        f'Cannot sell {quantity} from line item {line_item_id}. '
                        f'Only {line_item.available_returned_to_sell} returned items available.'
                    )
                )

        return items

    def save(self):
        """Sell multiple returned items."""
        order = self.context['order']
        data = self.validated_data
        user = self.context.get('request').user if self.context.get('request') else None

        from djmoney.money import Money

        conversions = []

        for item_data in data['items']:
            line_item = models.LoanOrderLineItem.objects.get(
                pk=item_data['line_item'], order=order
            )

            quantity = Decimal(str(item_data['quantity']))

            sale_price = None
            if 'sale_price' in item_data and item_data['sale_price']:
                # Get currency from existing sales order or default currency
                currency = (
                    data.get('existing_sales_order').customer.currency
                    if data.get('existing_sales_order')
                    else currency_code_default()
                )
                sale_price = Money(item_data['sale_price'], currency)

            conversion = line_item.sell_returned_items(
                quantity=quantity,
                user=user,
                sale_price=sale_price,
                existing_sales_order=data.get('existing_sales_order'),
                notes=data.get('notes', ''),
            )

            conversions.append(conversion)

        return conversions
