/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { mcOrderCommercialContext } from "./multicurrency_models";


patch(OrderSummary.prototype, {
    get multicurrencyTaxTotals() {
        const standard = this.currentOrder?.taxTotals;
        const context = mcOrderCommercialContext(this.currentOrder);

        if (!standard || !context.isNative) return standard;

        const convert = (value) => Number(value || 0) / context.rate;

        return {
            ...standard,
            currency_id: context.currencyId,
            tax_amount_currency: convert(standard.tax_amount_currency),
            order_total: convert(standard.order_total),
            order_rounding: convert(standard.order_rounding),
            subtotals: (standard.subtotals || []).map((subtotal) => ({
                ...subtotal,
                base_amount_currency: convert(subtotal.base_amount_currency),
                tax_groups: (subtotal.tax_groups || []).map((group) => ({
                    ...group,
                    base_amount_currency: convert(group.base_amount_currency),
                    tax_amount_currency: convert(group.tax_amount_currency),
                })),
            })),
        };
    },
});
