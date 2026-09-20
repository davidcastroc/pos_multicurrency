/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { useService } from "@web/core/utils/hooks";
import { useState, onWillStart } from "@odoo/owl";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

import {
    mcRelationId,
    mcFormatCurrency,
    mcFindCurrency,
    mcOrderCommercialContext,
} from "./multicurrency_models";


patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");

        // OWL can evaluate callbacks created inside t-foreach without preserving
        // the component as `this`. Bind every method used as an event callback
        // so clicks/inputs always execute with the PaymentScreen instance.
        this.mcOnTenderInput = this.mcOnTenderInput.bind(this);
        this.mcOnTenderKeydown = this.mcOnTenderKeydown.bind(this);
        this.mcApplyTender = this.mcApplyTender.bind(this);
        this.mcChooseChangeCurrency = this.mcChooseChangeCurrency.bind(this);

        this.mcState = useState({
            ready: false,
            enabled: false,
            currencies: [],
            companyCurrencyId: false,
            changeCurrencyId: false,
            tenderAmount: "",
            rateSource: "",
            rateDate: "",
        });

        onWillStart(async () => {
            if (!this.pos.config.enable_pos_multicurrency) {
                this.mcState.ready = true;
                return;
            }

            const data = await this.orm.call(
                "pos.session",
                "get_multicurrency_bootstrap",
                [this.pos.config.id]
            );

            Object.assign(this.mcState, {
                ready: true,
                enabled: Boolean(data?.enabled),
                currencies: data?.currencies || [],
                companyCurrencyId: data?.company_currency_id || false,
                changeCurrencyId: data?.default_change_currency_id || false,
                rateSource: data?.rate_source || "",
                rateDate: data?.rate_date || "",
            });
        });
    },

    mcCurrencyData(id) {
        return this.mcState.currencies.find(
            (currency) => Number(currency.id) === Number(id)
        );
    },

    mcCompanyCurrency() {
        return this.mcCurrencyData(this.mcState.companyCurrencyId);
    },

    mcOrderContext() {
        return mcOrderCommercialContext(this.currentOrder);
    },

    mcOrderDisplayCurrency() {
        const context = this.mcOrderContext();
        return context.isNative
            ? context.currency
            : this.mcCompanyCurrency();
    },

    mcOrderTotalDisplay() {
        const context = this.mcOrderContext();
        if (context.isNative) {
            return mcFormatCurrency(context.currency, context.total);
        }
        return this.env.utils.formatCurrency(this.currentOrder.get_total_with_tax());
    },

    mcOrderTaxDisplay() {
        const context = this.mcOrderContext();
        if (context.isNative) {
            return mcFormatCurrency(context.currency, context.tax);
        }
        return this.env.utils.formatCurrency(this.currentOrder.get_total_tax());
    },

    mcOrderCompanyEquivalentDisplay() {
        const context = this.mcOrderContext();
        if (!context.isNative) return "";
        return this.env.utils.formatCurrency(context.companyTotal);
    },

    mcSelectedMethodCurrency(paymentMethod = this.selectedPaymentLine?.payment_method_id) {
        const raw = paymentMethod?.payment_currency_id;
        const id = mcRelationId(raw) || this.mcState.companyCurrencyId;
        return this.mcCurrencyData(id);
    },

    mcSelectedMethod() {
        return this.selectedPaymentLine?.payment_method_id || false;
    },

    mcMethodBadge(paymentMethod) {
        const currency = this.mcSelectedMethodCurrency(paymentMethod);
        if (!currency) return "";
        const kind = paymentMethod?.mc_kind || "";
        if (kind === "sinpe") return "SINPE · CRC";
        return currency.name || "";
    },

    mcPaymentRate(currency) {
        if (!currency) return { rate: 1, role: "same", label: "" };
        if (currency.is_company_currency) {
            return { rate: 1, role: "same", label: "1:1" };
        }

        const order = this.mcOrderContext();
        if (order.isNative && Number(order.currencyId) === Number(currency.id)) {
            return {
                rate: order.rate,
                role: "sell",
                label: `${this.mcState.rateSource || "TC"} · venta`,
            };
        }

        return {
            rate: Number(currency.buy_company_per_unit || currency.company_per_unit || 1),
            role: "buy",
            label: `${this.mcState.rateSource || "TC"} · compra`,
        };
    },

    mcChangeRate(currency) {
        if (!currency) return 1;
        if (currency.is_company_currency) return 1;

        const order = this.mcOrderContext();
        if (order.isNative && Number(order.currencyId) === Number(currency.id)) {
            return order.rate;
        }

        return Number(
            currency.sell_company_per_unit ||
            currency.company_per_unit ||
            1
        );
    },

    mcTenderDue(currency = this.mcSelectedMethodCurrency()) {
        if (!currency) return 0;
        const companyDue = Math.max(Number(this.currentOrder.get_due() || 0), 0);
        const info = this.mcPaymentRate(currency);
        return info.rate > 0 ? companyDue / info.rate : 0;
    },

    mcTenderDueDisplay() {
        const currency = this.mcSelectedMethodCurrency();
        if (!currency) return "";
        return mcFormatCurrency(currency, this.mcTenderDue(currency));
    },

    mcRateDisplay() {
        const currency = this.mcSelectedMethodCurrency();
        if (!currency || currency.is_company_currency) {
            const context = this.mcOrderContext();
            if (
                context.isNative &&
                context.currency &&
                this.mcCompanyCurrency()
            ) {
                return `1 ${context.currency.name} = ${mcFormatCurrency(
                    this.mcCompanyCurrency(),
                    context.rate
                )}`;
            }
            return "Sin conversión";
        }

        const info = this.mcPaymentRate(currency);
        return `1 ${currency.name} = ${mcFormatCurrency(
            this.mcCompanyCurrency(),
            info.rate
        )}`;
    },

    mcRateRoleDisplay() {
        return this.mcPaymentRate(this.mcSelectedMethodCurrency()).label;
    },

    mcShowPanel() {
        if (!this.mcState.enabled || !this.mcState.ready) return false;
        return Boolean(this.selectedPaymentLine || this.mcOrderContext().isNative);
    },

    async addNewPaymentLine(paymentMethod) {
        const result = await super.addNewPaymentLine(...arguments);
        if (!result || !this.mcState.enabled) return result;

        const currency = this.mcSelectedMethodCurrency(paymentMethod);
        const amount = this.mcTenderDue(currency);
        this.mcState.tenderAmount = amount.toFixed(currency?.decimal_places ?? 2);

        const line = this.selectedPaymentLine;
        if (line && currency && !currency.is_company_currency) {
            const info = this.mcPaymentRate(currency);
            line.setForeignAmount(currency, amount, info.rate, info.role);
        }

        return result;
    },

    mcOnTenderInput(ev) {
        this.mcState.tenderAmount = ev.target.value;
    },

    mcOnTenderKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.mcApplyTender();
        }
    },

    mcApplyTender() {
        const line = this.selectedPaymentLine;
        const currency = this.mcSelectedMethodCurrency();

        const amount = Number(
            String(this.mcState.tenderAmount || "").replace(",", ".")
        );

        if (!line || !currency || !(amount >= 0)) {
            this.dialog.add(AlertDialog, {
                title: _t("Monto inválido"),
                body: _t("Ingrese un monto válido."),
            });
            return;
        }

        const info = this.mcPaymentRate(currency);

        if (currency.is_company_currency) {
            const currencyRecord = mcFindCurrency(line, currency.id);

            line.update({
                payment_currency_id: currencyRecord || false,
                amount_currency: amount,
                exchange_rate_snapshot: 1,
                exchange_rate_role: "same",
            });
            line.set_amount(amount);
        } else {
            line.setForeignAmount(
                currency,
                amount,
                info.rate,
                info.role
            );
        }

        this.numberBuffer.reset();
    },

    mcAppliedEquivalentDisplay() {
        const currency = this.mcSelectedMethodCurrency();
        const amount = Number(
            String(this.mcState.tenderAmount || "0").replace(",", ".")
        );
        if (!currency || !(amount >= 0)) return "";
        const rate = this.mcPaymentRate(currency).rate;
        return this.env.utils.formatCurrency(amount * rate);
    },

    mcCurrentChangeCompany() {
        return Math.max(Number(this.currentOrder.get_change() || 0), 0);
    },

    mcChangeDisplay(currencyId) {
        const currency = this.mcCurrencyData(currencyId);
        if (!currency) return "";
        const rate = this.mcChangeRate(currency);
        const amount = rate > 0 ? this.mcCurrentChangeCompany() / rate : 0;
        return mcFormatCurrency(currency, amount);
    },

    mcChooseChangeCurrency(currencyId) {
        const currency = this.mcCurrencyData(currencyId);
        if (!currency) return;

        this.mcState.changeCurrencyId = Number(currencyId);
        const rate = this.mcChangeRate(currency);
        const companyAmount = this.mcCurrentChangeCompany();
        const nativeAmount = rate > 0 ? companyAmount / rate : 0;

        this.currentOrder.setMulticurrencyChange(
            currency,
            nativeAmount,
            companyAmount,
            rate
        );
    },

    async validateOrder() {
        if (this.mcState.enabled && this.mcCurrentChangeCompany() > 0) {
            const currency =
                this.mcCurrencyData(this.mcState.changeCurrencyId) ||
                this.mcCompanyCurrency();

            if (!currency) {
                this.dialog.add(AlertDialog, {
                    title: _t("Seleccione la moneda del vuelto"),
                    body: _t("Indique la moneda en la que se entregará el vuelto."),
                });
                return;
            }

            this.mcChooseChangeCurrency(currency.id);
        }

        return super.validateOrder(...arguments);
    },
});

// FE/Odoo safety: after sync/validation a finalized order is immutable.  Some
// UI flows can leave the invoice toggle reachable for a fraction of a second;
// ignore that late click instead of calling PosOrder.set_to_invoice(), which
// correctly raises "Finalized Order cannot be modified".
patch(PaymentScreen.prototype, {
    toggleIsToInvoice() {
        if (this.currentOrder?.finalized) {
            return;
        }
        return super.toggleIsToInvoice(...arguments);
    },
});
