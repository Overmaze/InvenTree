import { t } from '@lingui/core/macro';
import { useMemo } from 'react';

import { AddItemButton } from '@lib/components/AddItemButton';
import { ProgressBar } from '@lib/components/ProgressBar';
import { ApiEndpoints } from '@lib/enums/ApiEndpoints';
import { ModelType } from '@lib/enums/ModelType';
import { UserRoles } from '@lib/enums/Roles';
import { apiUrl } from '@lib/functions/Api';
import type { TableFilter } from '@lib/types/Filters';
import { formatCurrency } from '../../defaults/formatters';
import { useLoanOrderFields } from '../../forms/LoanOrderForms';
import { useCreateApiFormModal } from '../../hooks/UseForm';
import { useTable } from '../../hooks/UseTable';
import { useUserState } from '../../states/UserState';
import {
  CompanyColumn,
  CreatedByColumn,
  CreationDateColumn,
  DescriptionColumn,
  LineItemsProgressColumn,
  ProjectCodeColumn,
  ReferenceColumn,
  ResponsibleColumn,
  StatusColumn,
  TargetDateColumn
} from '../ColumnRenderers';
import {
  AssignedToMeFilter,
  CreatedAfterFilter,
  CreatedBeforeFilter,
  CreatedByFilter,
  HasProjectCodeFilter,
  MaxDateFilter,
  MinDateFilter,
  OrderStatusFilter,
  OutstandingFilter,
  OverdueFilter,
  ProjectCodeFilter,
  ResponsibleFilter
} from '../Filter';
import { InvenTreeTable } from '../InvenTreeTable';

export function LoanOrderTable({
  partId,
  borrowerCompanyId,
  params
}: Readonly<{
  partId?: number;
  borrowerCompanyId?: number;
  params?: any;
}>) {
  const table = useTable(!!partId ? 'loanorder-part' : 'loanorder-index');
  const user = useUserState();

  const tableFilters: TableFilter[] = useMemo(() => {
    const filters: TableFilter[] = [
      OrderStatusFilter({ model: ModelType.loanorder }),
      OutstandingFilter(),
      OverdueFilter(),
      AssignedToMeFilter(),
      MinDateFilter(),
      MaxDateFilter(),
      CreatedBeforeFilter(),
      CreatedAfterFilter(),
      {
        name: 'has_due_date',
        type: 'boolean',
        label: t`Has Due Date`,
        description: t`Show loans with a due date`
      },
      {
        name: 'has_return_date',
        type: 'boolean',
        label: t`Has Return Date`,
        description: t`Show loans with a return date`
      },
      HasProjectCodeFilter(),
      ProjectCodeFilter(),
      ResponsibleFilter(),
      CreatedByFilter()
    ];

    return filters;
  }, [partId]);

  const loanOrderFields = useLoanOrderFields({});

  const newLoanOrder = useCreateApiFormModal({
    url: ApiEndpoints.loan_order_list,
    title: t`Add Loan`,
    fields: loanOrderFields,
    initialData: {
      borrower_company: borrowerCompanyId
    },
    follow: true,
    modelType: ModelType.loanorder
  });

  const tableActions = useMemo(() => {
    return [
      <AddItemButton
        key='add-loan-order'
        tooltip={t`Add Loan`}
        onClick={() => newLoanOrder.open()}
        hidden={!user.hasAddRole(UserRoles.loan_order)}
      />
    ];
  }, [user]);

  const tableColumns = useMemo(() => {
    return [
      ReferenceColumn({}),
      {
        accessor: 'borrower_company__name',
        title: t`Borrower`,
        sortable: true,
        render: (record: any) => (
          <CompanyColumn company={record.borrower_company_detail} />
        )
      },
      DescriptionColumn({}),
      LineItemsProgressColumn({}),
      {
        accessor: 'total_shipped',
        title: t`Shipped`,
        sortable: true,
        render: (record: any) => (
          <ProgressBar
            progressLabel={true}
            value={record.total_shipped}
            maximum={record.total_quantity}
          />
        )
      },
      {
        accessor: 'total_returned',
        title: t`Returned`,
        sortable: true,
        render: (record: any) => (
          <ProgressBar
            progressLabel={true}
            value={record.total_returned}
            maximum={record.total_shipped}
          />
        )
      },
      StatusColumn({ model: ModelType.loanorder }),
      ProjectCodeColumn({
        defaultVisible: false
      }),
      CreationDateColumn({
        defaultVisible: false
      }),
      CreatedByColumn({
        defaultVisible: false
      }),
      {
        accessor: 'issue_date',
        title: t`Issue Date`,
        sortable: true,
        defaultVisible: false
      },
      TargetDateColumn({
        accessor: 'due_date',
        title: t`Due Date`
      }),
      {
        accessor: 'return_date',
        title: t`Return Date`,
        sortable: true
      },
      ResponsibleColumn({}),
      {
        accessor: 'total_price',
        title: t`Total Price`,
        sortable: true,
        render: (record: any) => {
          return formatCurrency(record.total_price, {
            currency:
              record.order_currency || record.borrower_company_detail?.currency
          });
        }
      }
    ];
  }, []);

  return (
    <>
      {newLoanOrder.modal}
      <InvenTreeTable
        url={apiUrl(ApiEndpoints.loan_order_list)}
        tableState={table}
        columns={tableColumns}
        props={{
          params: {
            borrower_company_detail: true,
            responsible_detail: true,
            part: partId,
            borrower_company: borrowerCompanyId,
            ...params
          },
          tableFilters: tableFilters,
          tableActions: tableActions,
          modelType: ModelType.loanorder,
          enableSelection: true,
          enableDownload: true,
          enableReports: true,
          enableLabels: true
        }}
      />
    </>
  );
}
