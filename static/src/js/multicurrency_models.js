/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductProduct } from "@point_of_sale/app/models/product_product";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

function relationId(value) {
    if (!value) return false;
    if (typeof value === "number") return value;
    if (Array.isArray(value)) return value[0];
    return value.id || false;
}

patch(ProductProduct.prototype, {
    get_price(pricelist, quantity, priceExtra = 0, recurring = false, listPrice = false, originalLine = false, relatedLines = []) {
        if (this.pos_use_foreign_currency && Number(this.pos_foreign_price) > 0) {
            return Number(this.pos_company_price_preview || 0) + Number(priceExtra || 0);
        }
        return super.get_price(pricelist, quantity, priceExtra, recurring, listPrice, originalLine, relatedLines);
    },
});

patch(PosOrderline.prototype, {
    setup(vals) {
        super.setup(...arguments);
        const product = this.product_id;
        if (product?.pos_use_foreign_currency && Number(product.pos_foreign_price) > 0) {
            const foreign = Number(vals.foreign_unit_price || product.pos_foreign_price || 0);
            const base = Number(this.price_unit || product.pos_company_price_preview || 0);
            this.update({
                sale_currency_id: relationId(vals.sale_currency_id) || relationId(product.pos_sale_currency_id),
                foreign_unit_price: foreign,
                foreign_subtotal: Number(vals.foreign_subtotal || foreign * Number(this.qty || 1)),
                exchange_rate_snapshot: Number(vals.exchange_rate_snapshot || (foreign ? base / foreign : 0)),
            });
            if (!vals.price_unit && base) {
                this.set_unit_price(base);
            }
        }
    },
    set_quantity(quantity, keepPrice) {
        const result = super.set_quantity(...arguments);
        if (this.foreign_unit_price) {
            this.foreign_subtotal = Number(this.foreign_unit_price) * Number(this.qty || 0) * (1 - Number(this.discount || 0) / 100);
        }
        return result;
    },
    set_discount(discount) {
        const result = super.set_discount(...arguments);
        if (this.foreign_unit_price) {
            this.foreign_subtotal = Number(this.foreign_unit_price) * Number(this.qty || 0) * (1 - Number(this.discount || 0) / 100);
        }
        return result;
    },
    getDisplayData() {
        const data = super.getDisplayData(...arguments);
        if (this.foreign_unit_price && this.sale_currency_id) {
            const currency = this.models["res.currency"].get(this.sale_currency_id.id || this.sale_currency_id);
            if (currency) {
                data.multicurrencyPrice = `${currency.symbol || currency.name} ${Number(this.foreign_unit_price).toFixed(currency.decimal_places ?? 2)}`;
            }
        }
        return data;
    },
});

patch(PosPayment.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.payment_currency_id = vals.payment_currency_id || false;
        this.amount_currency = Number(vals.amount_currency || 0);
        this.exchange_rate_snapshot = Number(vals.exchange_rate_snapshot || 0);
    },
    setForeignAmount(currency, amountCurrency, companyPerUnit) {
        this.update({
            payment_currency_id: currency,
            amount_currency: Number(amountCurrency || 0),
            exchange_rate_snapshot: Number(companyPerUnit || 0),
        });
        this.set_amount(Number(amountCurrency || 0) * Number(companyPerUnit || 0));
    },
    export_for_printing() {
        const data = super.export_for_printing(...arguments);
        if (this.payment_currency_id && this.amount_currency) {
            const currency = this.payment_currency_id;
            data.foreign_amount = `${currency.symbol || currency.name} ${Number(this.amount_currency).toFixed(currency.decimal_places ?? 2)}`;
        }
        return data;
    },
});

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.change_currency_id = vals.change_currency_id || false;
        this.change_amount_currency = Number(vals.change_amount_currency || 0);
        this.change_amount_company = Number(vals.change_amount_company || 0);
        this.exchange_rate_snapshot = Number(vals.exchange_rate_snapshot || 0);
    },
    setMulticurrencyChange(currency, amountCurrency, companyAmount, rate) {
        this.update({
            change_currency_id: currency,
            change_amount_currency: Number(amountCurrency || 0),
            change_amount_company: Number(companyAmount || 0),
            exchange_rate_snapshot: Number(rate || 0),
        });
    },
});
