"""Admin interface for loan models."""

from django.contrib import admin

from loan import models


@admin.register(models.LoanOrder)
class LoanOrderAdmin(admin.ModelAdmin):
    """Admin interface for LoanOrder model."""

    list_display = [
        'reference',
        'borrower_company',
        'status',
        'creation_date',
        'issue_date',
        'due_date',
        'return_date',
    ]

    list_filter = [
        'status',
        'creation_date',
        'issue_date',
        'due_date',
    ]

    search_fields = [
        'reference',
        'borrower_company__name',
        'description',
    ]

    readonly_fields = [
        'reference_int',
        'creation_date',
    ]

    raw_id_fields = [
        'borrower_company',
        'responsible',
        'contact',
        'address',
        'project_code',
        'created_by',
        'converted_sales_order',
    ]


@admin.register(models.LoanOrderLineItem)
class LoanOrderLineItemAdmin(admin.ModelAdmin):
    """Admin interface for LoanOrderLineItem model."""

    list_display = [
        'order',
        'part',
        'quantity',
        'shipped',
        'returned',
        'status',
    ]

    list_filter = [
        'status',
    ]

    search_fields = [
        'order__reference',
        'part__name',
        'reference',
    ]

    raw_id_fields = [
        'order',
        'part',
        'project_code',
    ]


@admin.register(models.LoanOrderAllocation)
class LoanOrderAllocationAdmin(admin.ModelAdmin):
    """Admin interface for LoanOrderAllocation model."""

    list_display = [
        'line',
        'item',
        'quantity',
        'returned',
    ]

    search_fields = [
        'line__order__reference',
        'item__part__name',
    ]

    raw_id_fields = [
        'line',
        'item',
    ]


@admin.register(models.LoanOrderExtraLine)
class LoanOrderExtraLineAdmin(admin.ModelAdmin):
    """Admin interface for LoanOrderExtraLine model."""

    list_display = [
        'order',
        'description',
        'quantity',
        'price',
    ]

    search_fields = [
        'order__reference',
        'description',
        'reference',
    ]

    raw_id_fields = [
        'order',
    ]


@admin.register(models.LoanOrderLineConversion)
class LoanOrderLineConversionAdmin(admin.ModelAdmin):
    """Admin interface for LoanOrderLineConversion model."""

    list_display = [
        'loan_line',
        'quantity',
        'converted_date',
        'converted_by',
        'is_returned_items',
        'conversion_price',
    ]

    list_filter = [
        'is_returned_items',
        'converted_date',
    ]

    search_fields = [
        'loan_line__order__reference',
        'loan_line__part__name',
        'notes',
    ]

    readonly_fields = [
        'converted_date',
    ]

    raw_id_fields = [
        'loan_line',
        'sales_order_line',
        'converted_by',
    ]
