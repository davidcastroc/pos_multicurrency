/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { OpeningControlPopup } from "@point_of_sale/app/store/opening_control_popup/opening_control_popup";
import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";

function num(value) {
    const n = Number(String(value ?? "0").replace(",", "."));
    return Number.isFinite(n) ? n : 0;
}
function relationId(value) {
    if (!value) return false;
    if (typeof value === "number") return value;
    if (Array.isArray(value)) return value[0];
    return value.id || false;
}
function fmt(row, value) {
    const digits = Number.isInteger(row?.decimal_places) ? row.decimal_places : 2;
    const n = Number(value || 0).toLocaleString(undefined, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    });
    const symbol = row?.symbol || row?.name || "";
    return row?.position === "after" ? `${n} ${symbol}` : `${symbol} ${n}`;
}
function companyCurrencyId(pos) {
    return relationId(pos?.company?.currency_id) || relationId(pos?.currency);
}
function sessionId(pos) {
    return relationId(pos?.session) || relationId(pos?.config?.current_session_id);
}
async function loadCashState(component, target) {
    const sid = sessionId(component.pos);
    if (!sid) {
        target.ready = true;
        return;
    }
    try {
        const rows = await component.pos.data.call("pos.session", "mc_get_session_cash_state", [sid]);
        const safeRows = Array.isArray(rows) ? rows : [];
        target.rows.splice(0, target.rows.length, ...safeRows.map((r) => ({
            ...r,
            input: String(r.counted || r.opening_amount || 0),
            methods: (r.methods || []).map((m) => ({ ...m, confirmed: "0" })),
        })));
    } catch (error) {
        console.error("POS Multimoneda: no se pudo cargar el arqueo por moneda", error);
    } finally {
        target.ready = true;
    }
}

const shared = {
    mcFmt(row, value) { return fmt(row, value); },
    mcCompanyRow(rows) {
        const id = companyCurrencyId(this.pos);
        return (rows || []).find((r) => Number(r.currency_id) === Number(id));
    },
    mcForeignRows(rows) {
        const id = companyCurrencyId(this.pos);
        return (rows || []).filter((r) => Number(r.currency_id) !== Number(id));
    },
    mcRateText(rows) {
        const usd = (rows || []).find((r) => r.name === "USD");
        if (!usd || !usd.usd_sell_rate) return "";
        return `1 USD = ₡ ${Number(usd.usd_sell_rate).toFixed(2)}`;
    },
    mcRateMeta(rows) {
        const usd = (rows || []).find((r) => r.name === "USD");
        if (!usd) return "";
        const source = usd.rate_source || "BCCR";
        const date = usd.rate_date || "";
        return date ? `${source} · ${date}` : source;
    },
};

patch(OpeningControlPopup.prototype, {
    ...shared,
    setup() {
        super.setup(...arguments);
        this.mcOpening = useState({ ready: false, rows: [] });
        if (this.pos?.config?.enable_pos_multicurrency) {
            loadCashState(this, this.mcOpening).then(() => {
                for (const row of this.mcOpening.rows) row.input = String(row.opening_amount || 0);
            });
        }
    },
    mcOpeningOtherRows() { return this.mcForeignRows(this.mcOpening.rows); },
    async confirm() {
        if (this.pos?.config?.enable_pos_multicurrency && this.mcOpening.ready) {
            const companyId = companyCurrencyId(this.pos);
            const payload = this.mcOpening.rows.map((r) => ({
                currency_id: r.currency_id,
                amount: Number(r.currency_id) === Number(companyId) ? num(this.state.openingCash) : num(r.input),
            }));
            await this.pos.data.call("pos.session", "mc_set_opening_balances", [sessionId(this.pos), payload]);
        }
        return super.confirm(...arguments);
    },
});

patch(ClosePosPopup.prototype, {
    ...shared,
    setup() {
        super.setup(...arguments);
        this.mcClosing = useState({ ready: false, rows: [] });
        if (this.pos?.config?.enable_pos_multicurrency) loadCashState(this, this.mcClosing);
    },
    mcClosingOtherRows() { return this.mcForeignRows(this.mcClosing.rows); },
    mcDifference(row) { return num(row.input) - Number(row.expected || 0); },
    mcIsForeignMethod(pm) {
        // closing_control_data sends plain dictionaries for the native closing rows.
        // Those dictionaries do not reliably contain our custom mc_kind or
        // payment_currency_id fields.  The multicurrency cash-state payload DOES
        // contain the authoritative physical-currency grouping, so match by the
        // payment-method id first.  This removes Efectivo/Tarjeta/Transferencia USD
        // from Odoo's CRC-formatted native loop without relying on missing fields.
        const pmId = Number(pm?.id || 0);
        if (pmId && this.mcClosing?.ready) {
            const isInForeignRow = this.mcForeignRows(this.mcClosing.rows).some((row) =>
                (row?.methods || []).some((method) => Number(method.id) === pmId)
            );
            if (isInForeignRow) return true;
        }

        // Fallback for payloads where the custom fields are available.
        const kind = String(pm?.mc_kind || "");
        if (kind.endsWith("_usd")) return true;
        const currencyId = relationId(pm?.payment_currency_id);
        return Boolean(currencyId) && Number(currencyId) !== Number(companyCurrencyId(this.pos));
    },
    mcForeignMethods(row) {
        return row?.methods || [];
    },
    mcAllMethods() {
        return (this.mcClosing?.rows || []).flatMap((row) =>
            (row.methods || []).map((method) => ({ row, method }))
        );
    },
    mcCashRows() {
        return (this.mcClosing?.rows || []).filter((row) =>
            (row.methods || []).some((method) => method.is_cash)
        );
    },
    mcIsCompanyRow(row) {
        return Number(row?.currency_id || 0) === Number(companyCurrencyId(this.pos) || 0);
    },
    mcRowCounted(row) {
        if (Number(row.currency_id) === Number(companyCurrencyId(this.pos))) {
            const id = this.props.default_cash_details?.id;
            return num(this.state.payments?.[id]?.counted);
        }
        return num(row.input);
    },
    mcRowDifference(row) {
        return this.mcRowCounted(row) - Number(row.expected || 0);
    },
    mcMethodDifference(method) {
        return num(method?.confirmed) - Number(method?.amount || 0);
    },
    mcStatus(diff) {
        const d = Number(diff || 0);
        if (Math.abs(d) < 0.00001) return "Cuadre correcto";
        return d > 0 ? "Sobrante" : "Faltante";
    },
    mcStatusClass(diff) {
        return Math.abs(Number(diff || 0)) < 0.00001 ? "ll-mc-ok" : "ll-mc-bad";
    },
    mcIsCashMethod(method) {
        return Boolean(method?.is_cash);
    },
    mcNonCashMethods() {
        return this.mcAllMethods().filter(({ method }) => !method.is_cash);
    },
    async closeSession() {
        if (this.pos?.config?.enable_pos_multicurrency && this.mcClosing.ready) {
            const companyId = companyCurrencyId(this.pos);

            // Feed the native Odoo bank reconciliation with the user's physical
            // confirmed amount. Foreign currencies are converted only for the
            // accounting difference sent by Odoo; the UI remains in physical currency.
            for (const pm of this.props.non_cash_payment_methods || []) {
                const found = this.mcAllMethods().find(({ method }) => Number(method.id) === Number(pm.id));
                if (!found || found.method.is_cash || !this.state.payments?.[pm.id]) continue;
                const physical = num(found.method.confirmed);
                const rate = Number(found.row.name === "USD" ? (found.row.usd_sell_rate || 1) : 1);
                this.state.payments[pm.id].counted = String(physical * rate);
            }
            const defaultId = this.props.default_cash_details?.id;
            const payload = this.mcClosing.rows.map((r) => ({
                currency_id: r.currency_id,
                amount: Number(r.currency_id) === Number(companyId)
                    ? num(this.state.payments?.[defaultId]?.counted)
                    : num(r.input),
            }));
            await this.pos.data.call("pos.session", "mc_set_closing_counts", [sessionId(this.pos), payload]);
        }
        return super.closeSession(...arguments);
    },
});

// Use our complete closing template explicitly. The backend data and component
// remain native; only the visual template is replaced so foreign physical
// currencies are never formatted with the company-currency formatter.
ClosePosPopup.template = "pos_multicurrency.ClosePosPopup";
