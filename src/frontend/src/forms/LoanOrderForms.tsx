import { t } from '@lingui/core/macro';
import {
  IconAddressBook,
  IconCalendar,
  IconCoins,
  IconUser,
  IconUsers
} from '@tabler/icons-react';
import { useEffect, useMemo, useState } from 'react';

import { ApiEndpoints } from '@lib/enums/ApiEndpoints';
import { ModelType } from '@lib/enums/ModelType';
import { toNumber } from '@lib/functions/Conversion';
import type {
  ApiFormAdjustFilterType,
  ApiFormFieldSet,
  ApiFormFieldType
} from '@lib/types/Forms';
import { useGlobalSettingsState } from '../states/SettingsStates';

export function useLoanOrderFields({
  duplicateOrderId
}: {
  duplicateOrderId?: number;
}): ApiFormFieldSet {
  const globalSettings = useGlobalSettingsState();

  return useMemo(() => {
    const fields: ApiFormFieldSet = {
      reference: {},
      description: {},
      borrower_company: {
        disabled: duplicateOrderId != undefined,
        filters: {
          is_customer: true,
          active: true
        }
      },
      project_code: {},
      order_currency: {},
      due_date: {
        icon: <IconCalendar />
      },
      link: {},
      contact: {
        icon: <IconUser />,
        adjustFilters: (value: ApiFormAdjustFilterType) => {
          return {
            ...value.filters,
            company: value.data.borrower_company
          };
        }
      },
      address: {
        icon: <IconAddressBook />,
        adjustFilters: (value: ApiFormAdjustFilterType) => {
          return {
            ...value.filters,
            company: value.data.borrower_company
          };
        }
      },
      responsible: {
        icon: <IconUsers />
      }
    };

    // Order duplication fields
    if (!!duplicateOrderId) {
      fields.duplicate = {
        children: {
          order_id: {
            hidden: true,
            value: duplicateOrderId
          },
          copy_lines: {},
          copy_extra_lines: {}
        }
      };
    }

    if (!globalSettings.isSet('PROJECT_CODES_ENABLED', true)) {
      delete fields.project_code;
    }

    return fields;
  }, [duplicateOrderId, globalSettings]);
}

export function useLoanOrderLineItemFields({
  borrowerCompanyId,
  orderId,
  create,
  currency
}: {
  borrowerCompanyId?: number;
  orderId?: number;
  create?: boolean;
  currency?: string;
}): ApiFormFieldSet {
  const [loanPrice, setLoanPrice] = useState<string | undefined>(undefined);
  const [partCurrency, setPartCurrency] = useState<string>(currency ?? '');
  const [part, setPart] = useState<any>({});
  const [quantity, setQuantity] = useState<string>('1');

  // Update suggested loan price when part, quantity, or currency changes
  useEffect(() => {
    if (!create) return;

    const qty = toNumber(quantity, null);

    if (qty == null || qty <= 0) {
      setLoanPrice(undefined);
      return;
    }

    if (!part || !part.price_breaks || part.price_breaks.length === 0) {
      setLoanPrice(undefined);
      return;
    }

    const applicablePriceBreaks = part?.price_breaks
      ?.filter(
        (pb: any) => pb.price_currency == partCurrency && qty >= pb.quantity
      )
      .sort((a: any, b: any) => b.quantity - a.quantity);

    if (applicablePriceBreaks.length) {
      setLoanPrice(applicablePriceBreaks[0].price);
    } else {
      setLoanPrice(undefined);
    }
  }, [part, quantity, partCurrency, create]);

  return useMemo(() => {
    const fields: ApiFormFieldSet = {
      order: {
        filters: {
          borrower_company_detail: true
        },
        disabled: true,
        value: create ? orderId : undefined
      },
      part: {
        filters: {
          active: true,
          salable: true,
          price_breaks: true
        },
        onValueChange: (_: any, record?: any) => setPart(record)
      },
      reference: {},
      quantity: {
        onValueChange: (value) => {
          setQuantity(value);
        }
      },
      loan_price: {
        placeholder: loanPrice,
        placeholderAutofill: true
      },
      loan_price_currency: {
        icon: <IconCoins />,
        value: partCurrency,
        onValueChange: setPartCurrency
      },
      project_code: {
        description: t`Select project code for this line item`
      },
      target_date: {},
      notes: {},
      link: {}
    };

    return fields;
  }, [loanPrice, partCurrency, orderId, create]);
}

export function useLoanOrderAllocationFields({
  orderId
}: {
  orderId?: number;
}): ApiFormFieldSet {
  return useMemo(() => {
    return {
      item: {
        disabled: true
      },
      quantity: {}
    };
  }, [orderId]);
}

export function useLoanOrderExtraLineFields(): ApiFormFieldSet {
  return useMemo(() => {
    return {
      order: {
        disabled: true
      },
      quantity: {},
      reference: {},
      description: {},
      notes: {},
      price: {},
      price_currency: {
        icon: <IconCoins />
      },
      link: {}
    };
  }, []);
}
