/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductProduct } from "@point_of_sale/app/models/product_product";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";


function field(record, name, fallback = false) {
    if (!record) {
        return fallback;
    }

    const direct = record[name];
    if (direct !== undefined && direct !== null && direct !== false) {
        return direct;
    }

    const raw = record.raw?.[name];
    if (raw !== undefined && raw !== null && raw !== false) {
        return raw;
    }

    return fallback;
}


function relationId(value) {
    if (!value) {
        return false;
    }

    if (typeof value === "number") {
        return value;
    }

    if (Array.isArray(value)) {
        return value[0] || false;
    }

    return value.id || value.raw?.id || false;
}


function formatNative(currency, amount) {
    if (!currency) {
        return "";
    }

    const decimals = Number(currency.decimal_places ?? currency.raw?.decimal_places ?? 2);
    const symbol = currency.symbol || currency.raw?.symbol || currency.name || currency.raw?.name || "";
    const position = currency.position || currency.raw?.position || "before";
    const formatted = Number(amount || 0).toFixed(decimals);

    return position === "after"
        ? `${formatted} ${symbol}`
        : `${symbol} ${formatted}`;
}


function productNativeData(product) {
    const enabled = Boolean(field(product, "pos_use_foreign_currency", false));
    const nativePrice = Number(field(product, "pos_foreign_price", 0));
    const currencyValue = field(product, "pos_sale_currency_id", false);
    const currencyId = relationId(currencyValue);

    return {
        enabled,
        nativePrice,
        currencyId,
    };
}


patch(ProductProduct.prototype, {
    get_price(
        pricelist,
        quantity,
        priceExtra = 0,
        recurring = false,
        listPrice = false,
        originalLine = false,
        relatedLines = []
    ) {
        const native = productNativeData(this);

        if (native.enabled && native.nativePrice > 0) {
            return (
                Number(field(this, "pos_company_price_preview", 0)) +
                Number(priceExtra || 0)
            );
        }

        return super.get_price(
            pricelist,
            quantity,
            priceExtra,
            recurring,
            listPrice,
            originalLine,
            relatedLines
        );
    },
});


patch(PosOrderline.prototype, {
    setup(vals = {}) {
        super.setup(...arguments);

        const product = this.product_id;
        const native = productNativeData(product);

        if (!native.enabled || native.nativePrice <= 0) {
            return;
        }

        const nativeUnitPrice = Number(
            vals.foreign_unit_price ||
            this.foreign_unit_price ||
            native.nativePrice
        );

        const companyUnitPrice = Number(
            vals.price_unit ||
            this.price_unit ||
            field(product, "pos_company_price_preview", 0)
        );

        this.update({
            sale_currency_id:
                relationId(vals.sale_currency_id) ||
                relationId(this.sale_currency_id) ||
                native.currencyId,
            foreign_unit_price: nativeUnitPrice,
            foreign_subtotal: Number(
                vals.foreign_subtotal ||
                nativeUnitPrice * Number(this.qty || 1)
            ),
            exchange_rate_snapshot: Number(
                vals.exchange_rate_snapshot ||
                (
                    nativeUnitPrice > 0
                        ? companyUnitPrice / nativeUnitPrice
                        : 0
                )
            ),
        });

        if (!vals.price_unit && companyUnitPrice > 0) {
            this.set_unit_price(companyUnitPrice);
        }
    },

    _getNativeCurrency() {
        const product = this.product_id;
        const native = productNativeData(product);

        const currencyId =
            relationId(this.sale_currency_id) ||
            native.currencyId;

        if (!currencyId) {
            return false;
        }

        const currencyModel = this.models?.["res.currency"];

        if (!currencyModel) {
            return false;
        }

        const directCurrency = currencyModel.get?.(currencyId);

        if (directCurrency) {
            return directCurrency;
        }

        return (
            currencyModel
                .getAll?.()
                .find(
                    (currency) =>
                        Number(currency?.id || currency?.raw?.id) ===
                        Number(currencyId)
                ) ||
            false
        );
    },

    _getNativeUnitPrice() {
        const product = this.product_id;
        const native = productNativeData(product);

        return Number(
            this.foreign_unit_price ||
            native.nativePrice ||
            0
        );
    },

    _getNativeSubtotal() {
        const unitPrice = this._getNativeUnitPrice();
        const quantity = Number(this.qty || 0);
        const discountFactor = 1 - Number(this.discount || 0) / 100;

        return unitPrice * quantity * discountFactor;
    },

    _refreshForeignSubtotal() {
        const unitPrice = this._getNativeUnitPrice();

        if (unitPrice <= 0) {
            return;
        }

        this.foreign_unit_price = unitPrice;
        this.foreign_subtotal = this._getNativeSubtotal();
    },

    set_quantity() {
        const result = super.set_quantity(...arguments);
        this._refreshForeignSubtotal();
        return result;
    },

    set_discount() {
        const result = super.set_discount(...arguments);
        this._refreshForeignSubtotal();
        return result;
    },

    getDisplayData() {
    const data = super.getDisplayData(...arguments);
    const product = this.product_id;
    const native = productNativeData(product);

    if (!native.enabled || native.nativePrice <= 0) {
        return data;
    }

    const currency = this._getNativeCurrency();

    if (!currency) {
        return data;
    }

    const unitPrice = this._getNativeUnitPrice();
    const subtotal = this._getNativeSubtotal();

    data.price = formatNative(currency, subtotal);
    data.unitPrice = formatNative(currency, unitPrice);

    return data;
},
});
