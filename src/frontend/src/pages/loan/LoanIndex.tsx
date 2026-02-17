import { t } from '@lingui/core/macro';
import { Stack } from '@mantine/core';
import { useLocalStorage } from '@mantine/hooks';
import {
  IconAlertTriangle,
  IconBuildingStore,
  IconClockExclamation,
  IconTransfer
} from '@tabler/icons-react';
import { useMemo } from 'react';

import { UserRoles } from '@lib/enums/Roles';
import PermissionDenied from '../../components/errors/PermissionDenied';
import { PageDetail } from '../../components/nav/PageDetail';
import { PanelGroup } from '../../components/panels/PanelGroup';
import { useUserState } from '../../states/UserState';
import { CompanyTable } from '../../tables/company/CompanyTable';
import { LoanOrderTable } from '../../tables/loan/LoanOrderTable';

export default function LoanIndex() {
  const user = useUserState();

  const [tab, setTab] = useLocalStorage<string>({
    key: 'loan-index-tab',
    defaultValue: 'loanorders'
  });

  const panels = useMemo(() => {
    return [
      {
        name: 'loanorders',
        label: t`Loans`,
        icon: <IconTransfer />,
        content: <LoanOrderTable />
      },
      {
        name: 'pending',
        label: t`Pending`,
        icon: <IconClockExclamation />,
        content: (
          <LoanOrderTable params={{ outstanding: true }} />
        )
      },
      {
        name: 'overdue',
        label: t`Overdue`,
        icon: <IconAlertTriangle />,
        content: (
          <LoanOrderTable params={{ overdue: true }} />
        )
      },
      {
        name: 'borrowers',
        label: t`Borrowers`,
        icon: <IconBuildingStore />,
        content: (
          <CompanyTable
            path='loan/borrower'
            params={{ is_customer: true }}
          />
        )
      }
    ];
  }, [user]);

  if (!user.isLoggedIn() || !user.hasViewRole(UserRoles.loan_order)) {
    return <PermissionDenied />;
  }

  return (
    <Stack>
      <PageDetail title={t`Loans`} />
      <PanelGroup
        pageKey='loan-index'
        panels={panels}
        model='loanorder'
        id={null}
      />
    </Stack>
  );
}
