import { t } from '@lingui/core/macro';
import { Accordion, Grid, Skeleton, Stack, Text } from '@mantine/core';
import {
  IconInfoCircle,
  IconList
} from '@tabler/icons-react';
import { type ReactNode, useMemo } from 'react';
import { useParams } from 'react-router-dom';

import { ApiEndpoints } from '@lib/enums/ApiEndpoints';
import { ModelType } from '@lib/enums/ModelType';
import { UserRoles } from '@lib/enums/Roles';
import { apiUrl } from '@lib/functions/Api';
import AdminButton from '../../components/buttons/AdminButton';
import PrimaryActionButton from '../../components/buttons/PrimaryActionButton';
import { PrintingActions } from '../../components/buttons/PrintingActions';
import {
  type DetailsField,
  DetailsTable
} from '../../components/details/Details';
import { DetailsImage } from '../../components/details/DetailsImage';
import { ItemDetailsGrid } from '../../components/details/ItemDetails';
import {
  BarcodeActionDropdown,
  CancelItemAction,
  DuplicateItemAction,
  EditItemAction,
  HoldItemAction,
  OptionsActionDropdown
} from '../../components/items/ActionDropdown';
import { StylishText } from '../../components/items/StylishText';
import InstanceDetail from '../../components/nav/InstanceDetail';
import { PageDetail } from '../../components/nav/PageDetail';
import AttachmentPanel from '../../components/panels/AttachmentPanel';
import NotesPanel from '../../components/panels/NotesPanel';
import type { PanelType } from '../../components/panels/Panel';
import { PanelGroup } from '../../components/panels/PanelGroup';

import { RenderAddress } from '../../components/render/Company';
import { StatusRenderer } from '../../components/render/StatusRenderer';
import { formatCurrency } from '../../defaults/formatters';
import {
  useLoanOrderExtraLineFields,
  useLoanOrderFields
} from '../../forms/LoanOrderForms';
import {
  useCreateApiFormModal,
  useEditApiFormModal
} from '../../hooks/UseForm';
import { useInstance } from '../../hooks/UseInstance';
import useStatusCodes from '../../hooks/UseStatusCodes';
import { useGlobalSettingsState } from '../../states/SettingsStates';
import { useUserState } from '../../states/UserState';
import ExtraLineItemTable from '../../tables/general/ExtraLineItemTable';
import { LoanOrderLineItemTable } from '../../tables/loan/LoanOrderLineItemTable';

/**
 * Detail page for a single LoanOrder
 */
export default function LoanOrderDetail() {
  const { id } = useParams();

  const user = useUserState();

  const globalSettings = useGlobalSettingsState();

  const {
    instance: order,
    instanceQuery,
    refreshInstance
  } = useInstance({
    endpoint: ApiEndpoints.loan_order_list,
    pk: id,
    params: {
      borrower_company_detail: true,
      contact_detail: true,
      address_detail: true
    }
  });

  const orderCurrency = useMemo(() => {
    return (
      order.order_currency ||
      order.borrower_company_detail?.currency ||
      globalSettings.getSetting('INVENTREE_DEFAULT_CURRENCY')
    );
  }, [order, globalSettings]);

  const detailsPanel = useMemo(() => {
    if (instanceQuery.isFetching) {
      return <Skeleton />;
    }

    const tl: DetailsField[] = [
      {
        type: 'text',
        name: 'reference',
        label: t`Reference`,
        copy: true
      },
      {
        type: 'link',
        name: 'borrower_company',
        icon: 'customers',
        label: t`Borrower`,
        model: ModelType.company
      },
      {
        type: 'text',
        name: 'description',
        label: t`Description`,
        copy: true
      },
      {
        type: 'status',
        name: 'status',
        label: t`Status`,
        model: ModelType.loanorder
      },
      {
        type: 'status',
        name: 'status_custom_key',
        label: t`Custom Status`,
        model: ModelType.loanorder,
        icon: 'status',
        hidden:
          !order.status_custom_key || order.status_custom_key == order.status
      }
    ];

    const tr: DetailsField[] = [
      {
        type: 'progressbar',
        name: 'completed_lines',
        icon: 'progress',
        label: t`Completed Line Items`,
        total: order.line_items,
        progress: order.completed_lines || 0,
        hidden: !order.line_items
      },
      {
        type: 'progressbar',
        name: 'total_shipped',
        icon: 'progress',
        label: t`Shipped Items`,
        total: order.total_quantity || 0,
        progress: order.total_shipped || 0,
        hidden: !order.total_quantity
      },
      {
        type: 'progressbar',
        name: 'total_returned',
        icon: 'progress',
        label: t`Returned Items`,
        total: order.total_shipped || 0,
        progress: order.total_returned || 0,
        hidden: !order.total_shipped
      },
      {
        type: 'text',
        name: 'currency',
        label: t`Order Currency`,
        value_formatter: () => orderCurrency
      },
      {
        type: 'text',
        name: 'total_price',
        label: t`Total Cost`,
        value_formatter: () => {
          return formatCurrency(order?.total_price, {
            currency: orderCurrency
          });
        }
      }
    ];

    const bl: DetailsField[] = [
      {
        type: 'link',
        external: true,
        name: 'link',
        label: t`Link`,
        copy: true,
        hidden: !order.link
      },
      {
        type: 'text',
        name: 'address',
        label: t`Shipping Address`,
        icon: 'address',
        value_formatter: () =>
          order.address_detail ? (
            <RenderAddress instance={order.address_detail} />
          ) : (
            <Text size='sm' c='red'>{t`Not specified`}</Text>
          )
      },
      {
        type: 'text',
        name: 'contact_detail.name',
        label: t`Contact`,
        icon: 'user',
        copy: true,
        hidden: !order.contact
      },
      {
        type: 'text',
        name: 'contact_detail.email',
        label: t`Contact Email`,
        icon: 'email',
        copy: true,
        hidden: !order.contact_detail?.email
      },
      {
        type: 'text',
        name: 'contact_detail.phone',
        label: t`Contact Phone`,
        icon: 'phone',
        copy: true,
        hidden: !order.contact_detail?.phone
      },
      {
        type: 'text',
        name: 'project_code_label',
        label: t`Project Code`,
        icon: 'reference',
        copy: true,
        hidden: !order.project_code
      },
      {
        type: 'text',
        name: 'responsible',
        label: t`Responsible`,
        badge: 'owner',
        hidden: !order.responsible
      }
    ];

    const br: DetailsField[] = [
      {
        type: 'date',
        name: 'creation_date',
        label: t`Creation Date`,
        copy: true,
        hidden: !order.creation_date
      },
      {
        type: 'date',
        name: 'issue_date',
        label: t`Issue Date`,
        icon: 'calendar',
        copy: true,
        hidden: !order.issue_date
      },
      {
        type: 'date',
        name: 'due_date',
        label: t`Due Date`,
        icon: 'calendar',
        hidden: !order.due_date,
        copy: true
      },
      {
        type: 'date',
        name: 'return_date',
        label: t`Return Date`,
        hidden: !order.return_date,
        copy: true
      }
    ];

    return (
      <ItemDetailsGrid>
        <Grid grow>
          <DetailsImage
            appRole={UserRoles.loan_order}
            apiPath={ApiEndpoints.company_list}
            src={order.borrower_company_detail?.image}
            pk={order.borrower_company}
          />
          <Grid.Col span={{ base: 12, sm: 8 }}>
            <DetailsTable fields={tl} item={order} />
          </Grid.Col>
        </Grid>
        <DetailsTable fields={tr} item={order} />
        <DetailsTable fields={bl} item={order} />
        <DetailsTable fields={br} item={order} />
      </ItemDetailsGrid>
    );
  }, [order, orderCurrency, instanceQuery]);

  const loStatus = useStatusCodes({ modelType: ModelType.loanorder });

  const lineItemsEditable: boolean = useMemo(() => {
    const orderOpen: boolean =
      order.status != loStatus.RETURNED && order.status != loStatus.CANCELLED;

    if (orderOpen) {
      return true;
    } else {
      return globalSettings.isSet('LOANORDER_EDIT_COMPLETED_ORDERS');
    }
  }, [globalSettings, order.status, loStatus]);

  const extraLineFields = useLoanOrderExtraLineFields();
  const loanOrderFields = useLoanOrderFields({});

  const editLoanOrder = useEditApiFormModal({
    url: ApiEndpoints.loan_order_list,
    pk: order.pk,
    title: t`Edit Loan`,
    fields: loanOrderFields,
    onFormSuccess: () => {
      refreshInstance();
    }
  });

  const duplicateOrderFields = useLoanOrderFields({
    duplicateOrderId: order.pk
  });

  const duplicateLoanOrderInitialData = useMemo(() => {
    const data = { ...order };
    delete data.reference;
    return data;
  }, [order]);

  const duplicateLoanOrder = useCreateApiFormModal({
    url: ApiEndpoints.loan_order_list,
    title: t`Add Loan`,
    fields: duplicateOrderFields,
    initialData: duplicateLoanOrderInitialData,
    follow: true,
    modelType: ModelType.loanorder
  });

  const orderPanels: PanelType[] = useMemo(() => {
    return [
      {
        name: 'detail',
        label: t`Order Details`,
        icon: <IconInfoCircle />,
        content: detailsPanel
      },
      {
        name: 'line-items',
        label: t`Parts on Loan`,
        icon: <IconList />,
        content: (
          <Accordion
            multiple={true}
            defaultValue={['line-items', 'extra-items']}
          >
            <Accordion.Item value='line-items' key='lineitems'>
              <Accordion.Control>
                <StylishText size='lg'>{t`Parts on Loan`}</StylishText>
              </Accordion.Control>
              <Accordion.Panel>
                <LoanOrderLineItemTable
                  orderId={order.pk}
                  orderDetailRefresh={refreshInstance}
                  currency={orderCurrency}
                  borrowerCompanyId={order.borrower_company}
                  editable={lineItemsEditable}
                  orderStatus={order.status}
                />
              </Accordion.Panel>
            </Accordion.Item>
            <Accordion.Item value='extra-items' key='extraitems'>
              <Accordion.Control>
                <StylishText size='lg'>{t`Extra Charges`}</StylishText>
              </Accordion.Control>
              <Accordion.Panel>
                <ExtraLineItemTable
                  endpoint={ApiEndpoints.loan_order_extra_line_list}
                  orderId={order.pk}
                  editable={lineItemsEditable}
                  orderDetailRefresh={refreshInstance}
                  currency={orderCurrency}
                  role={UserRoles.loan_order}
                  fieldOverrides={extraLineFields}
                />
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
        )
      },
      AttachmentPanel({
        model_type: ModelType.loanorder,
        model_id: order.pk
      }),
      NotesPanel({
        model_type: ModelType.loanorder,
        model_id: order.pk
      })
    ];
  }, [order, id, user, loStatus, user]);

  const approveOrder = useCreateApiFormModal({
    url: apiUrl(ApiEndpoints.loan_order_approve, order.pk),
    title: t`Approve Loan`,
    onFormSuccess: refreshInstance,
    preFormWarning: t`Approve this loan`,
    successMessage: t`Loan approved`
  });

  const issueOrder = useCreateApiFormModal({
    url: apiUrl(ApiEndpoints.loan_order_issue, order.pk),
    title: t`Issue Loan`,
    onFormSuccess: refreshInstance,
    preFormWarning: t`Issue this loan`,
    successMessage: t`Loan issued`
  });

  const cancelOrder = useCreateApiFormModal({
    url: apiUrl(ApiEndpoints.loan_order_cancel, order.pk),
    title: t`Cancel Loan`,
    onFormSuccess: refreshInstance,
    preFormWarning: t`Cancel this loan`,
    successMessage: t`Loan cancelled`
  });

  const holdOrder = useCreateApiFormModal({
    url: apiUrl(ApiEndpoints.loan_order_hold, order.pk),
    title: t`Hold Loan`,
    onFormSuccess: refreshInstance,
    preFormWarning: t`Place this loan on hold`,
    successMessage: t`Loan placed on hold`
  });

  const returnOrder = useCreateApiFormModal({
    url: apiUrl(ApiEndpoints.loan_order_return, order.pk),
    title: t`Return Loan`,
    onFormSuccess: refreshInstance,
    preFormWarning: t`Mark this loan as returned`,
    successMessage: t`Loan marked as returned`
  });

  const convertToSale = useCreateApiFormModal({
    url: apiUrl(ApiEndpoints.loan_order_convert, order.pk),
    title: t`Convert to Sale`,
    onFormSuccess: refreshInstance,
    preFormWarning: t`Convert this loan to a sales order`,
    successMessage: t`Loan converted to sale`,
    fields: {
      create_sales_order: {}
    }
  });

  const writeOffOrder = useCreateApiFormModal({
    url: apiUrl(ApiEndpoints.loan_order_write_off, order.pk),
    title: t`Write Off Loan`,
    onFormSuccess: refreshInstance,
    preFormWarning: t`Write off this loan`,
    successMessage: t`Loan written off`,
    fields: {
      reason: {}
    }
  });

  const loActions = useMemo(() => {
    const canEdit: boolean = user.hasChangeRole(UserRoles.loan_order);

    const canApprove: boolean =
      canEdit && order.status == loStatus.PENDING;

    const canIssue: boolean =
      canEdit &&
      (order.status == loStatus.PENDING ||
        order.status == loStatus.APPROVED ||
        order.status == loStatus.ON_HOLD);

    const canCancel: boolean =
      canEdit &&
      (order.status == loStatus.PENDING || order.status == loStatus.ON_HOLD);

    const canHold: boolean =
      canEdit &&
      (order.status == loStatus.PENDING ||
        order.status == loStatus.ISSUED ||
        order.status == loStatus.SHIPPED);

    const canReturn: boolean =
      canEdit &&
      (order.status == loStatus.ISSUED || order.status == loStatus.SHIPPED);

    const canConvert: boolean =
      canEdit &&
      (order.status == loStatus.ISSUED || order.status == loStatus.SHIPPED);

    const canWriteOff: boolean =
      canEdit &&
      (order.status == loStatus.ISSUED || order.status == loStatus.SHIPPED);

    return [
      <PrimaryActionButton
        title={t`Approve Loan`}
        icon='approve'
        hidden={!canApprove}
        color='green'
        onClick={approveOrder.open}
      />,
      <PrimaryActionButton
        title={t`Issue Loan`}
        icon='issue'
        hidden={!canIssue}
        color='blue'
        onClick={issueOrder.open}
      />,
      <PrimaryActionButton
        title={t`Return Loan`}
        icon='return'
        hidden={!canReturn}
        color='green'
        onClick={returnOrder.open}
      />,
      <PrimaryActionButton
        title={t`Convert to Sale`}
        icon='convert'
        hidden={!canConvert}
        color='purple'
        onClick={convertToSale.open}
      />,
      <AdminButton model={ModelType.loanorder} id={order.pk} />,
      <BarcodeActionDropdown
        model={ModelType.loanorder}
        pk={order.pk}
        hash={order?.barcode_hash}
      />,
      <PrintingActions
        modelType={ModelType.loanorder}
        items={[order.pk]}
        enableReports
        enableLabels
      />,
      <OptionsActionDropdown
        tooltip={t`Loan Actions`}
        actions={[
          EditItemAction({
            hidden: !canEdit,
            onClick: editLoanOrder.open,
            tooltip: t`Edit loan`
          }),
          DuplicateItemAction({
            hidden: !user.hasAddRole(UserRoles.loan_order),
            onClick: duplicateLoanOrder.open,
            tooltip: t`Duplicate loan`
          }),
          HoldItemAction({
            tooltip: t`Hold loan`,
            hidden: !canHold,
            onClick: holdOrder.open
          }),
          CancelItemAction({
            tooltip: t`Cancel loan`,
            hidden: !canCancel,
            onClick: cancelOrder.open
          }),
          {
            name: t`Write Off`,
            tooltip: t`Write off loan`,
            icon: 'cancel',
            hidden: !canWriteOff,
            onClick: () => writeOffOrder.open()
          }
        ]}
      />
    ];
  }, [user, order, loStatus, globalSettings]);

  const orderBadges: ReactNode[] = useMemo(() => {
    return instanceQuery.isLoading
      ? []
      : [
          <StatusRenderer
            status={order.status_custom_key}
            type={ModelType.loanorder}
            options={{ size: 'lg' }}
            key={order.pk}
          />
        ];
  }, [order, instanceQuery]);

  const subtitle: string = useMemo(() => {
    return order.borrower_company_detail?.name || '';
  }, [order]);

  return (
    <>
      {approveOrder.modal}
      {issueOrder.modal}
      {cancelOrder.modal}
      {holdOrder.modal}
      {returnOrder.modal}
      {convertToSale.modal}
      {writeOffOrder.modal}
      {editLoanOrder.modal}
      {duplicateLoanOrder.modal}
      <InstanceDetail
        query={instanceQuery}
        requiredRole={UserRoles.loan_order}
      >
        <Stack gap='xs'>
          <PageDetail
            title={`${t`Loan`}: ${order.reference}`}
            subtitle={subtitle}
            imageUrl={order.borrower_company_detail?.image}
            badges={orderBadges}
            actions={loActions}
            breadcrumbs={[{ name: t`Loan`, url: '/loan/' }]}
            lastCrumb={[
              { name: order.reference, url: `/loan/loan-order/${order.pk}` }
            ]}
            editAction={editLoanOrder.open}
            editEnabled={user.hasChangePermission(ModelType.loanorder)}
          />
          <PanelGroup
            pageKey='loanorder'
            panels={orderPanels}
            model={ModelType.loanorder}
            reloadInstance={refreshInstance}
            instance={order}
            id={order.pk}
          />
        </Stack>
      </InstanceDetail>
    </>
  );
}
