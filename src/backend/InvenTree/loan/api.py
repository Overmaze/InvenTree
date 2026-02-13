"""JSON API for the Loan app."""

import logging

from django.contrib.auth.models import User
from django.db.models import F, Q
from django.urls import include, path
from django.utils.translation import gettext_lazy as _

import django_filters.rest_framework.filters as rest_filters
from django_filters.rest_framework.filterset import FilterSet
from rest_framework import permissions, status
from rest_framework.response import Response

import common.models
import company.models
import stock.models as stock_models
from data_exporter.mixins import DataExportViewMixin
from generic.states.api import StatusView
from InvenTree.api import (
    BulkUpdateMixin,
    ListCreateDestroyAPIView,
    MetadataView,
    ParameterListMixin,
)
from InvenTree.fields import InvenTreeOutputOption, OutputConfiguration
from InvenTree.filters import (
    SEARCH_ORDER_FILTER,
    SEARCH_ORDER_FILTER_ALIAS,
    InvenTreeDateFilter,
)
from InvenTree.helpers import str2bool
from InvenTree.mixins import (
    CreateAPI,
    ListAPI,
    ListCreateAPI,
    OutputOptionsMixin,
    RetrieveUpdateDestroyAPI,
    SerializerContextMixin,
)
from loan import models, serializers
from loan.status_codes import (
    LoanOrderLineStatus,
    LoanOrderLineStatusGroups,
    LoanOrderStatus,
    LoanOrderStatusGroups,
)
from part.models import Part
from users.models import Owner

logger = logging.getLogger('inventree')


class LoanOrderFilter(FilterSet):
    """Custom filters for LoanOrderList endpoint."""

    class Meta:
        """Metaclass options."""

        model = models.LoanOrder
        fields = []

    # Filter against order status
    status = rest_filters.NumberFilter(label=_('Order Status'), method='filter_status')

    def filter_status(self, queryset, name, value):
        """Filter by integer status code."""
        q1 = Q(status=value, status_custom_key__isnull=True)
        q2 = Q(status_custom_key=value)
        return queryset.filter(q1 | q2).distinct()

    # Exact match for reference
    reference = rest_filters.CharFilter(
        label=_('Order Reference'), field_name='reference', lookup_expr='iexact'
    )

    assigned_to_me = rest_filters.BooleanFilter(
        label=_('Assigned to me'), method='filter_assigned_to_me'
    )

    def filter_assigned_to_me(self, queryset, name, value):
        """Filter by orders assigned to the current user."""
        owners = Owner.get_owners_matching_user(self.request.user)

        if str2bool(value):
            return queryset.filter(responsible__in=owners)
        return queryset.exclude(responsible__in=owners)

    overdue = rest_filters.BooleanFilter(label='overdue', method='filter_overdue')

    def filter_overdue(self, queryset, name, value):
        """Filter by overdue status (computed from due_date and OPEN status)."""
        if str2bool(value):
            return queryset.filter(models.LoanOrder.overdue_filter())
        return queryset.exclude(models.LoanOrder.overdue_filter())

    outstanding = rest_filters.BooleanFilter(
        label=_('Outstanding'), method='filter_outstanding'
    )

    def filter_outstanding(self, queryset, name, value):
        """Filter by outstanding (open) orders."""
        if str2bool(value):
            return queryset.filter(status__in=LoanOrderStatusGroups.OPEN)
        return queryset.exclude(status__in=LoanOrderStatusGroups.OPEN)

    project_code = rest_filters.ModelChoiceFilter(
        queryset=common.models.ProjectCode.objects.all(),
        field_name='project_code',
        label=_('Project Code'),
    )

    has_project_code = rest_filters.BooleanFilter(
        method='filter_has_project_code', label=_('Has Project Code')
    )

    def filter_has_project_code(self, queryset, name, value):
        """Filter by whether or not the order has a project code."""
        if str2bool(value):
            return queryset.exclude(project_code=None)
        return queryset.filter(project_code=None)

    assigned_to = rest_filters.ModelChoiceFilter(
        queryset=Owner.objects.all(), field_name='responsible', label=_('Responsible')
    )

    created_by = rest_filters.ModelChoiceFilter(
        queryset=User.objects.all(), field_name='created_by', label=_('Created By')
    )

    created_before = InvenTreeDateFilter(
        label=_('Created Before'), field_name='creation_date', lookup_expr='lt'
    )

    created_after = InvenTreeDateFilter(
        label=_('Created After'), field_name='creation_date', lookup_expr='gt'
    )

    borrower_company = rest_filters.ModelChoiceFilter(
        queryset=company.models.Company.objects.all(),
        field_name='borrower_company',
        label=_('Borrower'),
    )

    due_before = InvenTreeDateFilter(
        label=_('Due Before'), field_name='due_date', lookup_expr='lt'
    )

    due_after = InvenTreeDateFilter(
        label=_('Due After'), field_name='due_date', lookup_expr='gt'
    )


class LoanOrderMixin(SerializerContextMixin):
    """Mixin class for LoanOrder endpoints."""

    queryset = models.LoanOrder.objects.all()
    serializer_class = serializers.LoanOrderSerializer

    def get_queryset(self, *args, **kwargs):
        """Return annotated queryset for this endpoint."""
        queryset = super().get_queryset(*args, **kwargs)

        queryset = queryset.prefetch_related(
            'borrower_company',
            'responsible',
            'contact',
            'address',
            'lines',
        )

        queryset = serializers.LoanOrderSerializer.annotate_queryset(queryset)

        return queryset


class LoanOrderOutputOptions(OutputConfiguration):
    """Output options for the LoanOrder endpoints."""

    OPTIONS = [
        InvenTreeOutputOption('borrower_company_detail'),
        InvenTreeOutputOption('responsible_detail'),
        InvenTreeOutputOption('contact_detail'),
        InvenTreeOutputOption('address_detail'),
        InvenTreeOutputOption('project_code_detail'),
        InvenTreeOutputOption('parameters'),
    ]


class OrderCreateMixin:
    """Mixin class which handles order creation via API."""

    def create(self, request, *args, **kwargs):
        """Save user information on order creation."""
        serializer = self.get_serializer(data=self.clean_data(request.data))
        serializer.is_valid(raise_exception=True)

        item = serializer.save()
        item.created_by = request.user
        item.save()

        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class LoanOrderList(
    LoanOrderMixin,
    OrderCreateMixin,
    DataExportViewMixin,
    OutputOptionsMixin,
    ParameterListMixin,
    ListCreateAPI,
):
    """API endpoint for accessing a list of LoanOrder objects.

    - GET: Return list of LoanOrder objects (with filters)
    - POST: Create a new LoanOrder
    """

    filterset_class = LoanOrderFilter
    filter_backends = SEARCH_ORDER_FILTER_ALIAS
    output_options = LoanOrderOutputOptions

    ordering_field_aliases = {
        'reference': ['reference_int', 'reference'],
        'project_code': ['project_code__code'],
    }

    filterset_fields = ['borrower_company']

    ordering_fields = [
        'creation_date',
        'created_by',
        'reference',
        'borrower_company__name',
        'status',
        'issue_date',
        'due_date',
        'return_date',
        'line_items',
        'total_price',
        'project_code',
    ]

    search_fields = [
        'borrower_company__name',
        'reference',
        'description',
        'project_code__code',
    ]

    ordering = '-reference'


class LoanOrderDetail(LoanOrderMixin, OutputOptionsMixin, RetrieveUpdateDestroyAPI):
    """API endpoint for detail view of a LoanOrder object."""

    output_options = LoanOrderOutputOptions


class LoanOrderContextMixin:
    """Mixin to add loan order object as serializer context variable."""

    def get_serializer_context(self):
        """Add order to the serializer context."""
        ctx = super().get_serializer_context()
        ctx['order'] = self.get_object()
        return ctx

    def get_object(self):
        """Return the LoanOrder instance."""
        if not hasattr(self, '_object'):
            self._object = models.LoanOrder.objects.get(pk=self.kwargs.get('pk'))
        return self._object


class LoanOrderIssue(LoanOrderContextMixin, CreateAPI):
    """API endpoint to issue a LoanOrder."""

    queryset = models.LoanOrder.objects.all()
    serializer_class = serializers.LoanOrderIssueSerializer

    def create(self, request, *args, **kwargs):
        """Issue the loan order and return the updated order."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        # Serialize the updated order with full details
        order_serializer = serializers.LoanOrderSerializer(order, context=self.get_serializer_context())
        return Response(order_serializer.data, status=status.HTTP_200_OK)


class LoanOrderHold(LoanOrderContextMixin, CreateAPI):
    """API endpoint to place a LoanOrder on hold."""

    queryset = models.LoanOrder.objects.all()
    serializer_class = serializers.LoanOrderHoldSerializer

    def create(self, request, *args, **kwargs):
        """Place the loan order on hold and return the updated order."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        # Serialize the updated order with full details
        order_serializer = serializers.LoanOrderSerializer(order, context=self.get_serializer_context())
        return Response(order_serializer.data, status=status.HTTP_200_OK)


class LoanOrderCancel(LoanOrderContextMixin, CreateAPI):
    """API endpoint to cancel a LoanOrder."""

    queryset = models.LoanOrder.objects.all()
    serializer_class = serializers.LoanOrderCancelSerializer

    def create(self, request, *args, **kwargs):
        """Cancel the loan order and return the updated order."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        # Serialize the updated order with full details
        order_serializer = serializers.LoanOrderSerializer(order, context=self.get_serializer_context())
        return Response(order_serializer.data, status=status.HTTP_200_OK)


class LoanOrderReturn(LoanOrderContextMixin, CreateAPI):
    """API endpoint to mark a LoanOrder as returned."""

    queryset = models.LoanOrder.objects.all()
    serializer_class = serializers.LoanOrderReturnSerializer

    def create(self, request, *args, **kwargs):
        """Mark the loan order as returned and return the updated order."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        # Serialize the updated order with full details
        order_serializer = serializers.LoanOrderSerializer(order, context=self.get_serializer_context())
        return Response(order_serializer.data, status=status.HTTP_200_OK)


class LoanOrderConvert(LoanOrderContextMixin, CreateAPI):
    """API endpoint to convert a LoanOrder to a SalesOrder."""

    queryset = models.LoanOrder.objects.all()
    serializer_class = serializers.LoanOrderConvertSerializer

    def create(self, request, *args, **kwargs):
        """Convert the loan order to a sale and return the updated order."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        # Serialize the updated order with full details
        order_serializer = serializers.LoanOrderSerializer(order, context=self.get_serializer_context())
        return Response(order_serializer.data, status=status.HTTP_200_OK)


class LoanOrderWriteOff(LoanOrderContextMixin, CreateAPI):
    """API endpoint to write off a LoanOrder."""

    queryset = models.LoanOrder.objects.all()
    serializer_class = serializers.LoanOrderWriteOffSerializer

    def create(self, request, *args, **kwargs):
        """Write off the loan order and return the updated order."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        # Serialize the updated order with full details
        order_serializer = serializers.LoanOrderSerializer(order, context=self.get_serializer_context())
        return Response(order_serializer.data, status=status.HTTP_200_OK)


class LoanOrderApprove(LoanOrderContextMixin, CreateAPI):
    """API endpoint to approve a LoanOrder.

    Only users with superuser permission can approve loan orders.
    """

    queryset = models.LoanOrder.objects.all()
    serializer_class = serializers.LoanOrderApproveSerializer
    permission_classes = [permissions.IsAdminUser]

    def create(self, request, *args, **kwargs):
        """Approve the loan order and return the updated order."""
        order = self.get_object()

        # Audit logging
        logger.info(
            f"Loan order approval initiated - Order: {order.reference} "
            f"(pk={order.pk}), User: {request.user.username} "
            f"(pk={request.user.pk}), Status: {order.status}"
        )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        # Audit logging - approval successful
        logger.info(
            f"Loan order approved successfully - Order: {order.reference} "
            f"(pk={order.pk}), User: {request.user.username}, "
            f"New Status: {order.status}"
        )

        # Serialize the updated order with full details
        order_serializer = serializers.LoanOrderSerializer(
            order, context=self.get_serializer_context()
        )
        return Response(order_serializer.data, status=status.HTTP_200_OK)


class LoanOrderConvertItems(LoanOrderContextMixin, CreateAPI):
    """API endpoint to batch convert multiple loan line items to sales."""

    queryset = models.LoanOrder.objects.all()
    serializer_class = serializers.LoanOrderConvertItemsSerializer

    def create(self, request, *args, **kwargs):
        """Convert multiple line items to sales and return conversion details."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversions = serializer.save()

        # Return the conversions
        conversion_serializer = serializers.LoanOrderLineConversionSerializer(
            conversions, many=True, context=self.get_serializer_context()
        )
        return Response(conversion_serializer.data, status=status.HTTP_200_OK)


class LoanOrderSellReturnedItems(LoanOrderContextMixin, CreateAPI):
    """API endpoint to batch sell multiple returned items."""

    queryset = models.LoanOrder.objects.all()
    serializer_class = serializers.LoanOrderSellReturnedItemsSerializer

    def create(self, request, *args, **kwargs):
        """Sell multiple returned items and return conversion details."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversions = serializer.save()

        # Return the conversions
        conversion_serializer = serializers.LoanOrderLineConversionSerializer(
            conversions, many=True, context=self.get_serializer_context()
        )
        return Response(conversion_serializer.data, status=status.HTTP_200_OK)


class LoanOrderShipItems(LoanOrderContextMixin, CreateAPI):
    """API endpoint to ship items out on loan."""

    queryset = models.LoanOrder.objects.all()
    serializer_class = serializers.LoanOrderShipItemsSerializer

    def create(self, request, *args, **kwargs):
        """Ship items and return the updated order with allocation details."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        allocations = serializer.save()

        # Refresh the order from database
        order = self.get_object()
        order.refresh_from_db()

        # Serialize the updated order with full details
        order_serializer = serializers.LoanOrderSerializer(order, context=self.get_serializer_context())

        # Return order data with created allocations
        return Response({
            'order': order_serializer.data,
            'allocations': serializers.LoanOrderAllocationSerializer(allocations, many=True).data
        }, status=status.HTTP_200_OK)


class LoanOrderShipAll(LoanOrderContextMixin, CreateAPI):
    """API endpoint to auto-allocate and ship all pending line items."""

    queryset = models.LoanOrder.objects.all()
    serializer_class = serializers.LoanOrderShipAllSerializer

    def create(self, request, *args, **kwargs):
        """Ship all pending items and return the updated order."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        allocations = serializer.save()

        # Refresh the order from database
        order = self.get_object()
        order.refresh_from_db()

        order_serializer = serializers.LoanOrderSerializer(
            order, context=self.get_serializer_context()
        )

        return Response({
            'order': order_serializer.data,
            'allocations': serializers.LoanOrderAllocationSerializer(
                allocations, many=True
            ).data,
        }, status=status.HTTP_200_OK)


class LoanOrderReturnItems(LoanOrderContextMixin, CreateAPI):
    """API endpoint to return items from loan."""

    queryset = models.LoanOrder.objects.all()
    serializer_class = serializers.LoanOrderReturnItemsSerializer

    def create(self, request, *args, **kwargs):
        """Return items and return the updated order with stock item details."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        returned_items = serializer.save()

        # Refresh the order from database
        order = self.get_object()
        order.refresh_from_db()

        # Serialize the updated order with full details
        order_serializer = serializers.LoanOrderSerializer(order, context=self.get_serializer_context())

        # Return order data with returned stock items
        import stock.serializers
        return Response({
            'order': order_serializer.data,
            'returned_items': stock.serializers.StockItemSerializer(returned_items, many=True).data
        }, status=status.HTTP_200_OK)


# Line Item endpoints

class LoanOrderLineItemFilter(FilterSet):
    """Custom filters for LoanOrderLineItemList endpoint."""

    class Meta:
        """Metaclass options."""

        model = models.LoanOrderLineItem
        fields = []

    order = rest_filters.ModelChoiceFilter(
        queryset=models.LoanOrder.objects.all(), field_name='order', label=_('Order')
    )

    part = rest_filters.ModelChoiceFilter(
        queryset=Part.objects.all(),
        field_name='part',
        label=_('Part'),
        method='filter_part',
    )

    def filter_part(self, queryset, name, part):
        """Filter by selected part."""
        include_variants = str2bool(self.data.get('include_variants', False))

        if include_variants:
            parts = part.get_descendants(include_self=True)
        else:
            parts = Part.objects.filter(pk=part.pk)

        return queryset.filter(part__in=parts)

    allocated = rest_filters.BooleanFilter(
        label=_('Allocated'), method='filter_allocated'
    )

    def filter_allocated(self, queryset, name, value):
        """Filter by lines which are 'allocated'."""
        q = Q(allocated__gte=F('quantity'))

        if str2bool(value):
            return queryset.filter(q)
        return queryset.exclude(q)

    shipped = rest_filters.BooleanFilter(
        label=_('Shipped'), method='filter_shipped'
    )

    def filter_shipped(self, queryset, name, value):
        """Filter by lines which have been shipped."""
        q = Q(shipped__gt=0)

        if str2bool(value):
            return queryset.filter(q)
        return queryset.exclude(q)

    returned = rest_filters.BooleanFilter(
        label=_('Returned'), method='filter_returned'
    )

    def filter_returned(self, queryset, name, value):
        """Filter by lines which have been returned."""
        q = Q(returned__gte=F('quantity'))

        if str2bool(value):
            return queryset.filter(q)
        return queryset.exclude(q)

    order_complete = rest_filters.BooleanFilter(
        label=_('Order Complete'), method='filter_order_complete'
    )

    def filter_order_complete(self, queryset, name, value):
        """Filter by whether the order is complete."""
        complete_statuses = LoanOrderStatusGroups.COMPLETE + LoanOrderStatusGroups.FAILED

        if str2bool(value):
            return queryset.filter(order__status__in=complete_statuses)
        return queryset.exclude(order__status__in=complete_statuses)

    order_outstanding = rest_filters.BooleanFilter(
        label=_('Order Outstanding'), method='filter_order_outstanding'
    )

    def filter_order_outstanding(self, queryset, name, value):
        """Filter by whether the order is outstanding."""
        if str2bool(value):
            return queryset.filter(order__status__in=LoanOrderStatusGroups.OPEN)
        return queryset.exclude(order__status__in=LoanOrderStatusGroups.OPEN)


class LoanOrderLineItemMixin(SerializerContextMixin):
    """Mixin class for LoanOrderLineItem endpoints."""

    queryset = models.LoanOrderLineItem.objects.all()
    serializer_class = serializers.LoanOrderLineItemSerializer

    def get_queryset(self, *args, **kwargs):
        """Return annotated queryset for this endpoint."""
        queryset = super().get_queryset(*args, **kwargs)

        queryset = queryset.prefetch_related(
            'part',
            'allocations',
            'allocations__item__part',
            'allocations__item__location',
            'order',
        )

        queryset = serializers.LoanOrderLineItemSerializer.annotate_queryset(queryset)

        return queryset


class LoanOrderLineItemOutputOptions(OutputConfiguration):
    """Output options for the LoanOrderLineItem endpoint."""

    OPTIONS = [
        InvenTreeOutputOption('part_detail'),
        InvenTreeOutputOption('order_detail'),
        InvenTreeOutputOption('borrower_company_detail'),
    ]


class LoanOrderLineItemList(
    LoanOrderLineItemMixin, DataExportViewMixin, OutputOptionsMixin, ListCreateAPI
):
    """API endpoint for accessing a list of LoanOrderLineItem objects."""

    filterset_class = LoanOrderLineItemFilter

    filter_backends = SEARCH_ORDER_FILTER_ALIAS

    output_options = LoanOrderLineItemOutputOptions

    ordering_fields = [
        'borrower_company',
        'order',
        'part',
        'part__name',
        'quantity',
        'allocated',
        'shipped',
        'returned',
        'reference',
        'loan_price',
        'target_date',
        'status',
    ]

    ordering_field_aliases = {
        'borrower_company': 'order__borrower_company__name',
        'part': 'part__name',
        'order': 'order__reference',
    }

    search_fields = ['part__name', 'quantity', 'reference']


class LoanOrderLineItemDetail(
    LoanOrderLineItemMixin, OutputOptionsMixin, RetrieveUpdateDestroyAPI
):
    """API endpoint for detail view of a LoanOrderLineItem object."""

    output_options = LoanOrderLineItemOutputOptions


# Allocation endpoints

class LoanOrderAllocationFilter(FilterSet):
    """Custom filters for LoanOrderAllocation endpoint."""

    class Meta:
        """Metaclass options."""

        model = models.LoanOrderAllocation
        fields = []

    order = rest_filters.NumberFilter(
        field_name='line__order', label=_('Order')
    )

    line = rest_filters.ModelChoiceFilter(
        queryset=models.LoanOrderLineItem.objects.all(),
        field_name='line',
        label=_('Line'),
    )

    item = rest_filters.ModelChoiceFilter(
        queryset=stock_models.StockItem.objects.all(),
        field_name='item',
        label=_('Stock Item'),
    )

    outstanding = rest_filters.BooleanFilter(
        label=_('Outstanding'), method='filter_outstanding'
    )

    def filter_outstanding(self, queryset, name, value):
        """Filter by outstanding allocations (still on loan)."""
        if str2bool(value):
            return queryset.filter(quantity__gt=0)
        return queryset.filter(quantity__lte=0)


class LoanOrderAllocationMixin(SerializerContextMixin):
    """Mixin class for LoanOrderAllocation endpoints."""

    queryset = models.LoanOrderAllocation.objects.all()
    serializer_class = serializers.LoanOrderAllocationSerializer

    def get_serializer(self, *args, **kwargs):
        """Return serializer with detail flags from query params."""
        try:
            params = self.request.query_params
            kwargs['item_detail'] = str2bool(params.get('item_detail', False))
            kwargs['part_detail'] = str2bool(params.get('part_detail', False))
            kwargs['line_detail'] = str2bool(params.get('line_detail', False))
            kwargs['order_detail'] = str2bool(params.get('order_detail', False))
        except AttributeError:
            pass

        return super().get_serializer(*args, **kwargs)

    def get_queryset(self, *args, **kwargs):
        """Return annotated queryset for this endpoint."""
        queryset = super().get_queryset(*args, **kwargs)

        queryset = queryset.prefetch_related(
            'line',
            'line__order',
            'line__order__borrower_company',
            'item',
            'item__part',
            'item__location',
        )

        return queryset


class LoanOrderAllocationList(
    LoanOrderAllocationMixin, DataExportViewMixin, ListCreateAPI
):
    """API endpoint for accessing a list of LoanOrderAllocation objects."""

    filterset_class = LoanOrderAllocationFilter
    filter_backends = SEARCH_ORDER_FILTER

    ordering_fields = [
        'quantity',
        'returned',
        'line',
        'item',
    ]


class LoanOrderAllocationDetail(LoanOrderAllocationMixin, RetrieveUpdateDestroyAPI):
    """API endpoint for detail view of a LoanOrderAllocation object."""

    pass


# Extra Line endpoints

class LoanOrderExtraLineList(DataExportViewMixin, ListCreateAPI):
    """API endpoint for accessing a list of LoanOrderExtraLine objects."""

    queryset = models.LoanOrderExtraLine.objects.all()
    serializer_class = serializers.LoanOrderExtraLineSerializer

    filter_backends = SEARCH_ORDER_FILTER

    ordering_fields = ['quantity', 'notes', 'reference']

    search_fields = ['quantity', 'notes', 'reference', 'description']

    filterset_fields = ['order']


class LoanOrderExtraLineDetail(RetrieveUpdateDestroyAPI):
    """API endpoint for detail view of a LoanOrderExtraLine object."""

    queryset = models.LoanOrderExtraLine.objects.all()
    serializer_class = serializers.LoanOrderExtraLineSerializer


# Status endpoint

class LoanOrderStatusView(StatusView):
    """API endpoint for LoanOrder status codes."""

    status_class = LoanOrderStatus


class LoanOrderLineStatusView(StatusView):
    """API endpoint for LoanOrderLine status codes."""

    status_class = LoanOrderLineStatus


# URL patterns

loan_order_api_urls = [
    # Loan order status endpoints
    path(
        'status/',
        include([
            path('', LoanOrderStatusView.as_view(), name='api-loan-order-status-list'),
        ]),
    ),
    path(
        'line-status/',
        include([
            path('', LoanOrderLineStatusView.as_view(), name='api-loan-order-line-status-list'),
        ]),
    ),
    # Loan order line item endpoints
    path(
        'line/',
        include([
            path('<int:pk>/', LoanOrderLineItemDetail.as_view(), name='api-loan-order-line-detail'),
            path('', LoanOrderLineItemList.as_view(), name='api-loan-order-line-list'),
        ]),
    ),
    # Loan order allocation endpoints
    path(
        'allocation/',
        include([
            path('<int:pk>/', LoanOrderAllocationDetail.as_view(), name='api-loan-order-allocation-detail'),
            path('', LoanOrderAllocationList.as_view(), name='api-loan-order-allocation-list'),
        ]),
    ),
    # Loan order extra line endpoints
    path(
        'extra-line/',
        include([
            path('<int:pk>/', LoanOrderExtraLineDetail.as_view(), name='api-loan-order-extra-line-detail'),
            path('', LoanOrderExtraLineList.as_view(), name='api-loan-order-extra-line-list'),
        ]),
    ),
    # Loan order detail endpoints (order-specific actions)
    path(
        '<int:pk>/',
        include([
            path('issue/', LoanOrderIssue.as_view(), name='api-loan-order-issue'),
            path('hold/', LoanOrderHold.as_view(), name='api-loan-order-hold'),
            path('cancel/', LoanOrderCancel.as_view(), name='api-loan-order-cancel'),
            path('return/', LoanOrderReturn.as_view(), name='api-loan-order-return'),
            path('convert/', LoanOrderConvert.as_view(), name='api-loan-order-convert'),
            path('write-off/', LoanOrderWriteOff.as_view(), name='api-loan-order-write-off'),
            path('approve/', LoanOrderApprove.as_view(), name='api-loan-order-approve'),
            path('convert-items/', LoanOrderConvertItems.as_view(), name='api-loan-order-convert-items'),
            path('sell-returned-items/', LoanOrderSellReturnedItems.as_view(), name='api-loan-order-sell-returned-items'),
            path('ship/', LoanOrderShipItems.as_view(), name='api-loan-order-ship'),
            path('ship-all/', LoanOrderShipAll.as_view(), name='api-loan-order-ship-all'),
            path('return-items/', LoanOrderReturnItems.as_view(), name='api-loan-order-return-items'),
            path('metadata/', MetadataView.as_view(model=models.LoanOrder), name='api-loan-order-metadata'),
            path('', LoanOrderDetail.as_view(), name='api-loan-order-detail'),
        ]),
    ),
    # Loan order list endpoint
    path('', LoanOrderList.as_view(), name='api-loan-order-list'),
]
