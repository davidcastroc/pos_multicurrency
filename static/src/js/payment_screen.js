/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { useService } from "@web/core/utils/hooks";
import { useState, onWillStart } from "@odoo/owl";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.mcState = useState({
            ready: false,
            enabled: false,
            currencies: [],
            companyCurrencyId: false,
            selectedPaymentCurrencyId: false,
            changeCurrencyId: false,
            foreignAmount: "",
        });
        onWillStart(async () => {
            if (!this.pos.config.enable_pos_multicurrency) return;
            const data = await this.orm.call("pos.session", "get_multicurrency_bootstrap", [this.pos.config.id]);
            this.mcState.enabled = Boolean(data.enabled);
            this.mcState.currencies = data.currencies || [];
            this.mcState.companyCurrencyId = data.company_currency_id;
            this.mcState.changeCurrencyId = data.default_change_currency_id;
            this.mcState.ready = true;
        });
    },

    currencyData(id) {
        return this.mcState.currencies.find((c) => Number(c.id) === Number(id));
    },

    selectedMethodCurrency(paymentMethod = this.selectedPaymentLine?.payment_method_id) {
        const id = paymentMethod?.payment_currency_id?.id || paymentMethod?.payment_currency_id;
        return this.currencyData(id || this.mcState.companyCurrencyId);
    },

    isForeignPaymentSelected() {
        const currency = this.selectedMethodCurrency();
        return Boolean(currency && !currency.is_company_currency);
    },

    async addNewPaymentLine(paymentMethod) {
        const result = await super.addNewPaymentLine(...arguments);
        if (!result || !this.mcState.enabled) return result;
        const currency = this.selectedMethodCurrency(paymentMethod);
        if (currency && !currency.is_company_currency) {
            this.mcState.selectedPaymentCurrencyId = currency.id;
            const due = Math.max(this.currentOrder.get_due(), 0);
            this.mcState.foreignAmount = currency.company_per_unit ? (due / currency.company_per_unit).toFixed(currency.decimal_places ?? 2) : "";
        } else {
            this.mcState.foreignAmount = "";
        }
        return result;
    },

    onForeignAmountInput(ev) {
        this.mcState.foreignAmount = ev.target.value;
    },

    applyForeignPayment() {
        const line = this.selectedPaymentLine;
        const currency = this.selectedMethodCurrency();
        const amount = Number(String(this.mcState.foreignAmount || "").replace(",", "."));
        if (!line || !currency || !(amount > 0) || !(currency.company_per_unit > 0)) {
            this.dialog.add(AlertDialog, {
                title: _t("Monto inválido"),
                body: _t("Ingrese un monto válido en la moneda seleccionada."),
            });
            return;
        }
        line.setForeignAmount(currency, amount, currency.company_per_unit);
        this.numberBuffer.reset();
    },

    formatForeign(currency, amount) {
        if (!currency) return "";
        return `${currency.symbol || currency.name} ${Number(amount || 0).toFixed(currency.decimal_places ?? 2)}`;
    },

    dueInCurrency(currency) {
        if (!currency?.company_per_unit) return 0;
        return Math.max(this.currentOrder.get_due(), 0) / currency.company_per_unit;
    },

    currentChangeCompany() {
        return Math.max(this.currentOrder.get_change(), 0);
    },

    currentChangeCurrency() {
        const currency = this.currencyData(this.mcState.changeCurrencyId);
        return currency?.company_per_unit ? this.currentChangeCompany() / currency.company_per_unit : 0;
    },

    chooseChangeCurrency(currencyId) {
        this.mcState.changeCurrencyId = Number(currencyId);
        const currency = this.currencyData(currencyId);
        this.currentOrder.setMulticurrencyChange(
            currency,
            this.currentChangeCurrency(),
            this.currentChangeCompany(),
            currency?.company_per_unit || 1
        );
    },

    async validateOrder(isForceValidate) {
        if (this.mcState.enabled && this.currentChangeCompany() > 0) {
            const currency = this.currencyData(this.mcState.changeCurrencyId);
            if (!currency) {
                this.dialog.add(AlertDialog, {
                    title: _t("Seleccione la moneda del vuelto"),
                    body: _t("Antes de validar, indique si el vuelto se entregará en colones o en dólares."),
                });
                return;
            }
            this.currentOrder.setMulticurrencyChange(
                currency,
                this.currentChangeCurrency(),
                this.currentChangeCompany(),
                currency.company_per_unit
            );
        }
        return super.validateOrder(...arguments);
    },
});
