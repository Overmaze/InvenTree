import { t } from '@lingui/core/macro';
import { IconPackageExport, IconPackageImport } from '@tabler/icons-react';
import { useCallback, useMemo, useState } from 'react';

import { ActionButton } from '@lib/components/ActionButton';
import { AddItemButton } from '@lib/components/AddItemButton';
import { ProgressBar } from '@lib/components/ProgressBar';
import {
  type RowAction,
  RowDeleteAction,
  RowEditAction
} from '@lib/components/RowActions';
import { ApiEndpoints } from '@lib/enums/ApiEndpoints';
import { ModelType } from '@lib/enums/ModelType';
import { UserRoles } from '@lib/enums/Roles';
import { apiUrl } from '@lib/functions/Api';
import { formatCurrency } from '../../defaults/formatters';
import { useLoanOrderLineItemFields } from '../../forms/LoanOrderForms';
import {
  useCreateApiFormModal,
  useDeleteApiFormModal,
  useEditApiFormModal
} from '../../hooks/UseForm';
import { useTable } from '../../hooks/UseTable';
import useStatusCodes from '../../hooks/UseStatusCodes';
import { useUserState } from '../../states/UserState';
import { RenderPartColumn, StatusColumn } from '../ColumnRenderers';
import { InvenTreeTable } from '../InvenTreeTable';

export function LoanOrderLineItemTable({
  orderId,
  orderDetailRefresh,
  currency,
  borrowerCompanyId,
  editable,
  orderStatus
}: {
  orderId: number;
  orderDetailRefresh: () => void;
  currency?: string;
  borrowerCompanyId?: number;
  editable?: boolean;
  orderStatus?: number;
}) {
  const table = useTable('loanorderlineitem');
  const user = useUserState();
  const [selectedLine, setSelectedLine] = useState<number>(0);
  const [selectedPartId, setSelectedPartId] = useState<number>(0);
  const [selectedShippedQty, setSelectedShippedQty] = useState<number>(0);
  const [selectedReturnedQty, setSelectedReturnedQty] = useState<number>(0);
  const [selectedQuantity, setSelectedQuantity] = useState<number>(0);

  const loStatus = useStatusCodes({ modelType: ModelType.loanorder });

  const canShip =
    user.hasChangeRole(UserRoles.loan_order) &&
    (orderStatus == loStatus.ISSUED ||
      orderStatus == loStatus.APPROVED ||
      orderStatus == loStatus.SHIPPED);

  const canReturn =
    user.hasChangeRole(UserRoles.loan_order) &&
    orderStatus != undefined &&
    orderStatus != loStatus.RETURNED &&
    orderStatus != loStatus.CANCELLED &&
    orderStatus != loStatus.WRITTEN_OFF;

  const lineItemFields = useLoanOrderLineItemFields({
    orderId,
    borrowerCompanyId,
    create: true,
    currency
  });

  const newLineItem = useCreateApiFormModal({
    url: ApiEndpoints.loan_order_line_list,
    title: t`Add Line Item`,
    fields: lineItemFields,
    initialData: {
      order: orderId
    },
    onFormSuccess: () => {
      orderDetailRefresh();
      table.refreshTable();
    },
    modelType: ModelType.loanorderlineitem
  });

  const editLineItemFields = useLoanOrderLineItemFields({
    orderId,
    borrowerCompanyId,
    create: false,
    currency
  });

  const editLineItem = useEditApiFormModal({
    url: ApiEndpoints.loan_order_line_list,
    pk: selectedLine,
    title: t`Edit Line Item`,
    fields: editLineItemFields,
    onFormSuccess: () => {
      orderDetailRefresh();
      table.refreshTable();
    }
  });

  const deleteLineItem = useDeleteApiFormModal({
    url: ApiEndpoints.loan_order_line_list,
    pk: selectedLine,
    title: t`Delete Line Item`,
    onFormSuccess: () => {
      orderDetailRefresh();
      table.refreshTable();
    }
  });

  // Ship items modal
  const shipItems = useCreateApiFormModal({
    url: apiUrl(ApiEndpoints.loan_order_ship, orderId),
    title: t`Ship Items`,
    fields: {
      stock_item: {
        filters: {
          part: selectedPartId,
          in_stock: true,
          available: true
        }
      },
      quantity: {}
    },
    initialData: {
      quantity: Math.max(0, (selectedQuantity || 0) - (selectedShippedQty || 0))
    },
    preFormWarning: t`Ship stock items to the borrower`,
    successMessage: t`Items shipped`,
    processFormData: (data: any) => {
      return {
        items: [
          {
            line_item: selectedLine,
            stock_item: data.stock_item,
            quantity: data.quantity
          }
        ]
      };
    },
    onFormSuccess: () => {
      orderDetailRefresh();
      table.refreshTable();
    }
  });

  // Return items modal
  const returnItems = useCreateApiFormModal({
    url: apiUrl(ApiEndpoints.loan_order_return_items, orderId),
    title: t`Return Items`,
    fields: {
      allocation: {
        filters: {
          line: selectedLine,
          outstanding: true
        }
      },
      quantity: {},
      location: {}
    },
    initialData: {
      quantity: Math.max(0, (selectedShippedQty || 0) - (selectedReturnedQty || 0))
    },
    preFormWarning: t`Return loaned items to stock`,
    successMessage: t`Items returned`,
    processFormData: (data: any) => {
      return {
        items: [
          {
            allocation: data.allocation,
            quantity: data.quantity
          }
        ],
        location: data.location || undefined
      };
    },
    onFormSuccess: () => {
      orderDetailRefresh();
      table.refreshTable();
    }
  });

  // Ship all items modal
  const shipAllItems = useCreateApiFormModal({
    url: apiUrl(ApiEndpoints.loan_order_ship_all, orderId),
    title: t`Ship All Items`,
    preFormWarning: t`Auto-allocate stock and ship all pending items to the borrower`,
    successMessage: t`All items shipped`,
    onFormSuccess: () => {
      orderDetailRefresh();
      table.refreshTable();
    }
  });

  const rowActions = useCallback(
    (record: any): RowAction[] => {
      const unshipped =
        (record.quantity || 0) - (record.shipped || 0);
      const onLoan =
        (record.shipped || 0) - (record.returned || 0);

      return [
        {
          title: t`Ship Items`,
          icon: <IconPackageExport />,
          color: 'blue',
          hidden: !canShip || unshipped <= 0,
          onClick: () => {
            setSelectedLine(record.pk);
            setSelectedPartId(record.part);
            setSelectedQuantity(record.quantity || 0);
            setSelectedShippedQty(record.shipped || 0);
            shipItems.open();
          }
        },
        {
          title: t`Return Items`,
          icon: <IconPackageImport />,
          color: 'green',
          hidden: !canReturn || onLoan <= 0,
          onClick: () => {
            setSelectedLine(record.pk);
            setSelectedShippedQty(record.shipped || 0);
            setSelectedReturnedQty(record.returned || 0);
            returnItems.open();
          }
        },
        RowEditAction({
          hidden: !editable || !user.hasChangeRole(UserRoles.loan_order),
          onClick: () => {
            setSelectedLine(record.pk);
            editLineItem.open();
          }
        }),
        RowDeleteAction({
          hidden: !editable || !user.hasDeleteRole(UserRoles.loan_order),
          onClick: () => {
            setSelectedLine(record.pk);
            deleteLineItem.open();
          }
        })
      ];
    },
    [canShip, canReturn, editable, user]
  );

  const tableActions = useMemo(() => {
    const canEdit = user.hasChangeRole(UserRoles.loan_order) && editable;

    return [
      <ActionButton
        key='ship-all-items'
        icon={<IconPackageExport />}
        tooltip={t`Ship All Items`}
        onClick={() => shipAllItems.open()}
        hidden={!canShip}
        color='blue'
      />,
      <AddItemButton
        key='add-line-item'
        tooltip={t`Add Line Item`}
        onClick={() => newLineItem.open()}
        hidden={!canEdit}
      />
    ];
  }, [user, editable, canShip]);

  const tableColumns = useMemo(() => {
    return [
      {
        accessor: 'part',
        title: t`Part`,
        sortable: true,
        render: (record: any) => <RenderPartColumn part={record.part_detail} />
      },
      {
        accessor: 'reference',
        title: t`Reference`
      },
      {
        accessor: 'quantity',
        title: t`Quantity`,
        sortable: true
      },
      {
        accessor: 'shipped',
        title: t`Shipped`,
        sortable: true,
        render: (record: any) => (
          <ProgressBar
            progressLabel
            value={record.shipped || 0}
            maximum={record.quantity || 0}
          />
        )
      },
      {
        accessor: 'returned',
        title: t`Returned`,
        sortable: true,
        render: (record: any) => (
          <ProgressBar
            progressLabel
            value={record.returned || 0}
            maximum={record.shipped || 0}
          />
        )
      },
      {
        accessor: 'on_loan',
        title: t`On Loan`,
        render: (record: any) => {
          const onLoan = (record.shipped || 0) - (record.returned || 0);
          return onLoan;
        }
      },
      StatusColumn({ model: ModelType.loanorderlineitem }),
      {
        accessor: 'loan_price',
        title: t`Unit Price`,
        sortable: true,
        render: (record: any) => {
          return formatCurrency(record.loan_price, {
            currency: record.loan_price_currency || currency
          });
        }
      },
      {
        accessor: 'total_price',
        title: t`Total Price`,
        render: (record: any) => {
          const total = (record.quantity || 0) * (record.loan_price || 0);
          return formatCurrency(total, {
            currency: record.loan_price_currency || currency
          });
        }
      },
      {
        accessor: 'target_date',
        title: t`Target Date`,
        sortable: true
      },
      {
        accessor: 'notes',
        title: t`Notes`
      }
    ];
  }, [currency]);

  return (
    <>
      {newLineItem.modal}
      {editLineItem.modal}
      {deleteLineItem.modal}
      {shipItems.modal}
      {shipAllItems.modal}
      {returnItems.modal}
      <InvenTreeTable
        url={apiUrl(ApiEndpoints.loan_order_line_list)}
        tableState={table}
        columns={tableColumns}
        props={{
          params: {
            order: orderId,
            part_detail: true
          },
          rowActions: rowActions,
          tableActions: tableActions,
          modelType: ModelType.loanorderlineitem,
          enableSelection: true
        }}
      />
    </>
  );
}
