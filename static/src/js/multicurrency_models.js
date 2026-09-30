/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductProduct } from "@point_of_sale/app/models/product_product";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { accountTaxHelpers } from "@account/helpers/account_tax";


export function mcRelationId(value) {
    if (!value) return false;
    if (typeof value === "number") return value;
    if (Array.isArray(value)) return value[0] || false;
    return value.id || value.raw?.id || false;
}

export function mcField(record, name, fallback = false) {
    if (!record) return fallback;
    const direct = record[name];
    if (direct !== undefined && direct !== null && direct !== false) return direct;
    const raw = record.raw?.[name];
    if (raw !== undefined && raw !== null && raw !== false) return raw;
    return fallback;
}

export function mcCurrencyModel(record) {
    return record?.models?.["res.currency"];
}

export function mcFindCurrency(record, id) {
    const model = mcCurrencyModel(record);
    if (!model || !id) return false;
    return (
        model.get?.(id) ||
        model.getAll?.().find((c) => Number(c.id || c.raw?.id) === Number(id)) ||
        false
    );
}


export function mcCurrencyRecord(record, currencyLike) {
    const id = mcRelationId(currencyLike);
    return id ? mcFindCurrency(record, id) : false;
}

export function mcFormatCurrency(currency, amount) {
    if (!currency) return "";
    const decimals = Number(currency.decimal_places ?? currency.raw?.decimal_places ?? 2);
    const symbol =
        currency.symbol ||
        currency.raw?.symbol ||
        currency.name ||
        currency.raw?.name ||
        "";
    const position = currency.position || currency.raw?.position || "before";
    const formatted = Number(amount || 0).toFixed(decimals);
    return position === "after" ? `${formatted} ${symbol}` : `${symbol} ${formatted}`;
}

export function mcConfig(record) {
    return record?.models?.["pos.config"]?.getAll?.()?.[0] || false;
}

export function mcProductNativeData(product) {
    const enabled = Boolean(mcField(product, "pos_use_foreign_currency", false));
    const nativePrice = Number(mcField(product, "pos_foreign_price", 0));
    const currencyId = mcRelationId(mcField(product, "pos_sale_currency_id", false));
    return { enabled, nativePrice, currencyId };
}

export function mcCompanyPerUnitForProduct(product) {
    const native = mcProductNativeData(product);
    if (!native.enabled || !(native.nativePrice > 0)) return 1;

    const currency = mcFindCurrency(product, native.currencyId);
    const config = mcConfig(product);
    const companyCurrency = config?.currency_id;
    const companyCurrencyId = mcRelationId(companyCurrency);

    if (native.currencyId === companyCurrencyId) return 1;

    const currencyName = currency?.name || currency?.raw?.name;
    const companyName = companyCurrency?.name || companyCurrency?.raw?.name;

    if (
        currencyName === "USD" &&
        companyName === "CRC" &&
        Number(config?.mc_usd_sell_rate || 0) > 0
    ) {
        return Number(config.mc_usd_sell_rate);
    }

    const preview = Number(mcField(product, "pos_company_price_preview", 0));
    return native.nativePrice > 0 && preview > 0 ? preview / native.nativePrice : 1;
}


export function mcTaxExcludedCompanyUnitForIncludedTarget(line, targetIncluded) {
    const target = Number(targetIncluded || 0);
    if (!(target > 0)) return target;

    // Match the standard POS behavior: when the POS is configured to display
    // totals with taxes included, the commercial foreign price is also treated
    // as the FINAL customer price, not as a tax-exclusive base.
    if (line?.config?.iface_tax_included !== "total") {
        return target;
    }

    const company = line.company;
    const product = line.product_id;
    const taxes = line.tax_ids || product?.taxes_id || [];

    if (!company || !product || !taxes?.length) {
        return target;
    }

    const baseLine = accountTaxHelpers.prepare_base_line_for_taxes_computation(
        line,
        line.prepareBaseLineForTaxesComputationExtraValues({
            price_unit: target,
            quantity: 1,
            discount: 0,
            tax_ids: taxes,
            special_mode: "total_included",
        })
    );

    accountTaxHelpers.add_tax_details_in_base_line(baseLine, company);
    accountTaxHelpers.round_base_lines_tax_details([baseLine], company);

    return Number(
        baseLine?.tax_details?.total_excluded_currency ?? target
    );
}

export function mcOrderCommercialContext(order) {
    if (!order?.lines?.length) return { isNative: false };

    const lines = order.lines.filter(
        (line) => Number(line.qty || 0) !== 0 && !line.combo_parent_id
    );
    if (!lines.length) return { isNative: false };

    const nativeLines = lines.filter((line) => {
        return (
            mcRelationId(line.sale_currency_id) &&
            Number(line.foreign_unit_price || 0) > 0 &&
            Number(line.exchange_rate_snapshot || 0) > 0
        );
    });
    if (nativeLines.length !== lines.length) return { isNative: false };

    const ids = new Set(nativeLines.map((line) => mcRelationId(line.sale_currency_id)));
    if (ids.size !== 1) return { isNative: false };

    const currencyId = [...ids][0];
    const currency = mcFindCurrency(order, currencyId);
    if (!currency) return { isNative: false };

    let nativeBase = 0;
    let companyBase = 0;
    for (const line of nativeLines) {
        const nativeSubtotal = Number(line.foreign_subtotal || 0);
        const rate = Number(line.exchange_rate_snapshot || 0);
        nativeBase += nativeSubtotal;
        companyBase += nativeSubtotal * rate;
    }

    // Refund lines make both nativeBase and companyBase negative.
    // Their quotient is still the correct positive exchange rate.
    // Only reject a zero native base.
    const rate = nativeBase !== 0 ? companyBase / nativeBase : 0;
    if (!(rate > 0)) return { isNative: false };

    const companyTotal = Number(order.get_total_with_tax?.() || 0);
    const companyTax = Number(order.get_total_tax?.() || 0);
    const companyUntaxed = Number(order.get_total_without_tax?.() || 0);
    const companyDue = Number(order.get_due?.() ?? order.getTotalDue?.() ?? companyTotal);

    return {
        isNative: true,
        currencyId,
        currency,
        rate,
        total: companyTotal / rate,
        tax: companyTax / rate,
        untaxed: companyUntaxed / rate,
        due: companyDue / rate,
        companyTotal,
        companyTax,
        companyUntaxed,
        companyDue,
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
        const native = mcProductNativeData(this);
        if (native.enabled && native.nativePrice > 0) {
            const rate = mcCompanyPerUnitForProduct(this);
            return native.nativePrice * rate + Number(priceExtra || 0);
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

        const native = mcProductNativeData(this.product_id);
        if (!native.enabled || !(native.nativePrice > 0)) return;

        const rate = Number(
            vals.exchange_rate_snapshot ||
            this.exchange_rate_snapshot ||
            mcCompanyPerUnitForProduct(this.product_id)
        );

        const nativeUnit = Number(
            vals.foreign_unit_price ||
            this.foreign_unit_price ||
            native.nativePrice
        );

        this.update({
            sale_currency_id:
                mcFindCurrency(this, native.currencyId) ||
                this.sale_currency_id ||
                false,
            foreign_unit_price: nativeUnit,
            foreign_subtotal:
                nativeUnit *
                Number(this.qty || 1) *
                (1 - Number(this.discount || 0) / 100),
            exchange_rate_snapshot: rate,
        });

        /*
         * El precio comercial nativo representa el price_unit comercial
         * del producto. Si el impuesto es price_include=True, Odoo debe
         * recibir el precio completo y separar internamente base + impuesto.
         *
         * Ejemplo:
         *   $30 x 450 = CRC 13,500 como price_unit
         *
         * Odoo calcula después:
         *   base + IVA incluido = CRC 13,500
         */
        const desiredCompanyPrice = nativeUnit * rate;

        if (desiredCompanyPrice > 0) {
            this.set_unit_price(desiredCompanyPrice);
        }
    },

    _mcNativeCurrency() {
        const id =
            mcRelationId(this.sale_currency_id) ||
            mcProductNativeData(this.product_id).currencyId;
        return mcFindCurrency(this, id);
    },

    _mcNativeUnitPrice() {
        return Number(
            this.foreign_unit_price ||
            mcProductNativeData(this.product_id).nativePrice ||
            0
        );
    },

    _mcRefreshForeignSubtotal() {
        const unit = this._mcNativeUnitPrice();
        if (!(unit > 0)) return;
        this.foreign_unit_price = unit;
        this.foreign_subtotal =
            unit *
            Number(this.qty || 0) *
            (1 - Number(this.discount || 0) / 100);
    },

    set_quantity() {
        const result = super.set_quantity(...arguments);
        this._mcRefreshForeignSubtotal();

        const native = mcProductNativeData(this.product_id);
        const rate = Number(
            this.exchange_rate_snapshot ||
            mcCompanyPerUnitForProduct(this.product_id)
        );
        const nativeUnit = this._mcNativeUnitPrice();

        if (native.enabled && nativeUnit > 0 && rate > 0) {
            /*
             * Igual que en setup(): price_unit conserva el precio comercial
             * completo convertido a moneda contable. El motor fiscal del POS
             * determina base e impuesto según price_include del impuesto.
             */
            const companyUnit = nativeUnit * rate;

            if (companyUnit > 0) {
                this.set_unit_price(companyUnit);
            }
        }

        return result;
    },

    set_discount() {
        const result = super.set_discount(...arguments);
        this._mcRefreshForeignSubtotal();
        return result;
    },

    getDisplayData() {
        const data = super.getDisplayData(...arguments);
        const native = mcProductNativeData(this.product_id);
        if (!native.enabled || !(native.nativePrice > 0)) return data;

        const currency = this._mcNativeCurrency();
        if (!currency) return data;

        const unit = this._mcNativeUnitPrice();
        const subtotal =
            unit *
            Number(this.qty || 0) *
            (1 - Number(this.discount || 0) / 100);

        /*
         * Orderline valida estrictamente el shape de getDisplayData().
         * Usamos únicamente las propiedades estándar de Odoo para mostrar
         * el precio comercial en su moneda nativa.
         */
        data.price = mcFormatCurrency(currency, subtotal);
        data.unitPrice = mcFormatCurrency(currency, unit);
        return data;
    },
});


patch(PosPayment.prototype, {
    setForeignAmount(currency, amountCurrency, companyPerUnit, role = "generic") {
        const nativeAmount = Number(amountCurrency || 0);
        const rate = Number(companyPerUnit || 0);

        const currencyRecord = mcCurrencyRecord(this, currency);

        this.update({
            payment_currency_id: currencyRecord || false,
            amount_currency: nativeAmount,
            exchange_rate_snapshot: rate,
            exchange_rate_role: role,
        });

        this.set_amount(nativeAmount * rate);
    },

    export_for_printing() {
        const data = super.export_for_printing(...arguments);
        const currencyId = mcRelationId(this.payment_currency_id);
        const currency = mcFindCurrency(this, currencyId);

        if (currency && Number(this.amount_currency || 0)) {
            data.mc_display = mcFormatCurrency(currency, this.amount_currency);
            data.mc_rate = Number(this.exchange_rate_snapshot || 0);
            data.mc_currency = currency.name || currency.raw?.name || "";
        }
        return data;
    },
});


patch(PosOrder.prototype, {
    setMulticurrencyChange(currency, nativeAmount, companyAmount, rate) {
        const currencyRecord = mcCurrencyRecord(this, currency);

        this.update({
            change_currency_id: currencyRecord || false,
            change_amount_currency: Number(nativeAmount || 0),
            change_amount_company: Number(companyAmount || 0),
            change_exchange_rate: Number(rate || 0),
        });
    },
});
