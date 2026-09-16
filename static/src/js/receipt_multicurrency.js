/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import {
    mcFormatCurrency,
    mcFindCurrency,
    mcRelationId,
    mcOrderCommercialContext,
} from "./multicurrency_models";


patch(PosOrder.prototype, {
    export_for_printing(baseUrl, headerData) {
        const data = super.export_for_printing(...arguments);
        const context = mcOrderCommercialContext(this);

        const mc = {
            singleNative: Boolean(context.isNative),
            totalDisplay: "",
            untaxedDisplay: "",
            taxDisplay: "",
            companyEquivalentDisplay: "",
            changeDisplay: "",
        };

        if (context.isNative) {
            mc.totalDisplay = mcFormatCurrency(context.currency, context.total);
            mc.untaxedDisplay = mcFormatCurrency(context.currency, context.untaxed);
            mc.taxDisplay = mcFormatCurrency(context.currency, context.tax);
            // PosOrder is a related-model record, not an OWL component.
            // It does not expose `this.env.utils`. Use the real order currency
            // record and our formatter instead.
            mc.companyEquivalentDisplay = mcFormatCurrency(
                this.currency,
                context.companyTotal
            );
        }

        const changeCurrencyId = mcRelationId(this.change_currency_id);
        const changeCurrency = mcFindCurrency(this, changeCurrencyId);
        if (changeCurrency && Number(this.change_amount_currency || 0) > 0) {
            mc.changeDisplay = mcFormatCurrency(
                changeCurrency,
                this.change_amount_currency
            );
        }

        data.mc = mc;
        return data;
    },
});
