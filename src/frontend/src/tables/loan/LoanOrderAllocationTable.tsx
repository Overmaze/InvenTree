import { t } from '@lingui/core/macro';
import { useMemo } from 'react';

import { ApiEndpoints } from '@lib/enums/ApiEndpoints';
import { ModelType } from '@lib/enums/ModelType';
import { apiUrl } from '@lib/functions/Api';
import { useTable } from '../../hooks/UseTable';
import { RenderStockLocation } from '../../components/render/Stock';
import { InvenTreeTable } from '../InvenTreeTable';

export function LoanOrderAllocationTable({
  orderId,
  showPartInfo = true,
  allowEdit = false
}: {
  orderId: number;
  showPartInfo?: boolean;
  allowEdit?: boolean;
}) {
  const table = useTable('loanorderallocation');

  const tableColumns = useMemo(() => {
    const columns: any[] = [];

    if (showPartInfo) {
      columns.push({
        accessor: 'item_detail.part_detail.name',
        title: t`Part`,
        sortable: false,
        render: (record: any) => {
          return record.item_detail?.part_detail?.full_name || '-';
        }
      });
    }

    columns.push(
      {
        accessor: 'item',
        title: t`Stock Item`,
        sortable: true,
        render: (record: any) => {
          if (!record.item_detail) return '-';
          return (
            <div>
              {record.item_detail.part_detail?.name}
              {record.item_detail.serial && ` [${record.item_detail.serial}]`}
            </div>
          );
        }
      },
      {
        accessor: 'location',
        title: t`Location`,
        render: (record: any) => {
          if (!record.item_detail?.location_detail) return '-';
          return <RenderStockLocation instance={record.item_detail.location_detail} />;
        }
      },
      {
        accessor: 'quantity',
        title: t`Allocated Quantity`,
        sortable: true
      },
      {
        accessor: 'returned',
        title: t`Returned`,
        sortable: true
      },
      {
        accessor: 'on_loan',
        title: t`On Loan`,
        render: (record: any) => {
          return (record.quantity || 0) - (record.returned || 0);
        }
      }
    );

    return columns;
  }, [showPartInfo]);

  return (
    <InvenTreeTable
      url={apiUrl(ApiEndpoints.loan_order_allocation_list)}
      tableState={table}
      columns={tableColumns}
      props={{
        params: {
          order: orderId,
          item_detail: true,
          part_detail: true
        },
        modelType: ModelType.loanorderallocation,
        enableSelection: allowEdit
      }}
    />
  );
}
