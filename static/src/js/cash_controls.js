/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { OpeningControlPopup } from "@point_of_sale/app/components/popups/opening_control_popup/opening_control_popup";
import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";

function num(value) {
    const n = Number(String(value ?? "0").replace(",", "."));
    return Number.isFinite(n) ? n : 0;
}
function fmt(row, value) {
    const n = Number(value || 0).toFixed(row.decimal_places ?? 2);
    return row.position === "after" ? `${n} ${row.symbol || row.name}` : `${row.symbol || row.name} ${n}`;
}

patch(OpeningControlPopup.prototype, {
    setup() {
        super.setup(...arguments);
        this.mcOpening = useState({ ready: false, rows: [] });
        if (this.pos.config.enable_pos_multicurrency) {
            this.pos.data.call("pos.session", "mc_get_session_cash_state", [this.pos.session.id]).then((rows) => {
                this.mcOpening.rows.splice(0, this.mcOpening.rows.length, ...rows.map((r) => ({ ...r, input: String(r.opening_amount || 0) })));
                this.mcOpening.ready = true;
            });
        }
    },
    mcOpeningOtherRows() {
        const companyId = this.pos.company.currency_id?.id || this.pos.currency?.id;
        return this.mcOpening.rows.filter((r) => Number(r.currency_id) !== Number(companyId));
    },
    mcFmt(row, value) { return fmt(row, value); },
    async confirm() {
        if (this.pos.config.enable_pos_multicurrency && this.mcOpening.ready) {
            const companyId = this.pos.company.currency_id?.id || this.pos.currency?.id;
            const payload = this.mcOpening.rows.map((r) => ({
                currency_id: r.currency_id,
                amount: Number(r.currency_id) === Number(companyId) ? num(this.state.openingCash) : num(r.input),
            }));
            await this.pos.data.call("pos.session", "mc_set_opening_balances", [this.pos.session.id, payload]);
        }
        return super.confirm(...arguments);
    },
});

patch(ClosePosPopup.prototype, {
    setup() {
        super.setup(...arguments);
        this.mcClosing = useState({ ready: false, rows: [] });
        if (this.pos.config.enable_pos_multicurrency) {
            this.pos.data.call("pos.session", "mc_get_session_cash_state", [this.pos.session.id]).then((rows) => {
                this.mcClosing.rows.splice(0, this.mcClosing.rows.length, ...rows.map((r) => ({ ...r, input: String(r.counted || 0) })));
                this.mcClosing.ready = true;
            });
        }
    },
    mcClosingOtherRows() {
        const companyId = this.pos.company.currency_id?.id || this.pos.currency?.id;
        return this.mcClosing.rows.filter((r) => Number(r.currency_id) !== Number(companyId));
    },
    mcFmt(row, value) { return fmt(row, value); },
    mcDifference(row) { return num(row.input) - Number(row.expected || 0); },
    async closeSession() {
        if (this.pos.config.enable_pos_multicurrency && this.mcClosing.ready) {
            const companyId = this.pos.company.currency_id?.id || this.pos.currency?.id;
            const payload = this.mcClosing.rows.map((r) => ({
                currency_id: r.currency_id,
                amount: Number(r.currency_id) === Number(companyId)
                    ? num(this.state.payments[this.props.default_cash_details?.id]?.counted)
                    : num(r.input),
            }));
            await this.pos.data.call("pos.session", "mc_set_closing_counts", [this.pos.session.id, payload]);
        }
        return super.closeSession(...arguments);
    },
});
