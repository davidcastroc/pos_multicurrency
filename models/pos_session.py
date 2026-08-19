# -*- coding: utf-8 -*-
from collections import defaultdict
from odoo import api, fields, models
from odoo.exceptions import UserError


class PosSession(models.Model):
    _inherit = "pos.session"

    currency_summary_ids = fields.One2many(
        "pos.session.currency.summary", "session_id", string="Arqueo por moneda", readonly=True
    )

    @api.model
    def get_multicurrency_bootstrap(self, config_id):
        config = self.env["pos.config"].browse(config_id).exists()
        if not config:
            raise UserError("No se encontró la configuración del Punto de Venta.")
        company = config.company_id
        company_currency = company.currency_id
        currencies = config.allowed_currency_ids | company_currency
        manual = {line.currency_id.id: line.company_per_unit for line in config.currency_rate_ids}
        date = fields.Date.context_today(self)
        values = []
        for currency in currencies:
            if currency == company_currency:
                rate = 1.0
            elif config.exchange_rate_source == "manual":
                rate = manual.get(currency.id)
                if not rate:
                    raise UserError(f"Falta la tasa manual para {currency.display_name}.")
            else:
                rate = currency._convert(1.0, company_currency, company, date, round=False)
            values.append({
                "id": currency.id, "name": currency.name, "symbol": currency.symbol,
                "position": currency.position, "decimal_places": currency.decimal_places,
                "company_per_unit": rate, "is_company_currency": currency == company_currency,
            })
        return {
            "enabled": config.enable_pos_multicurrency,
            "company_currency_id": company_currency.id,
            "default_change_currency_id": config.default_change_currency_id.id or company_currency.id,
            "show_native_product_prices": config.show_native_product_prices,
            "show_company_equivalent": config.show_company_equivalent,
            "currencies": values,
        }

    def action_refresh_currency_summary(self):
        self._rebuild_currency_summaries()
        return True

    def _rebuild_currency_summaries(self):
        Summary = self.env["pos.session.currency.summary"].sudo()
        for session in self:
            totals = defaultdict(lambda: {"received": 0.0, "change": 0.0, "company": 0.0})
            payments = self.env["pos.payment"].sudo().search([
                ("session_id", "=", session.id),
                ("pos_order_id.state", "not in", ["draft", "cancel"]),
            ])
            for payment in payments:
                currency = payment.payment_currency_id or session.company_id.currency_id
                native = payment.amount_currency if payment.payment_currency_id else payment.amount
                totals[currency.id]["received"] += native
                totals[currency.id]["company"] += payment.amount
            orders = self.env["pos.order"].sudo().search([
                ("session_id", "=", session.id), ("state", "not in", ["draft", "cancel"]),
                ("change_currency_id", "!=", False),
            ])
            for order in orders:
                totals[order.change_currency_id.id]["change"] += order.change_amount_currency
                totals[order.change_currency_id.id]["company"] -= order.change_amount_company
            Summary.search([("session_id", "=", session.id)]).unlink()
            Summary.create([{
                "session_id": session.id, "currency_id": currency_id,
                "amount_received": vals["received"], "change_given": vals["change"],
                "net_amount": vals["received"] - vals["change"],
                "company_currency_amount": vals["company"],
            } for currency_id, vals in totals.items()])


class PosSessionCurrencySummary(models.Model):
    _name = "pos.session.currency.summary"
    _description = "Arqueo por moneda de sesión POS"
    _order = "currency_id"

    session_id = fields.Many2one("pos.session", required=True, ondelete="cascade", index=True)
    currency_id = fields.Many2one("res.currency", string="Moneda física", required=True, readonly=True)
    amount_received = fields.Monetary(string="Recibido", currency_field="currency_id", readonly=True)
    change_given = fields.Monetary(string="Vuelto", currency_field="currency_id", readonly=True)
    net_amount = fields.Monetary(string="Neto esperado", currency_field="currency_id", readonly=True)
    company_currency_id = fields.Many2one(
        "res.currency", string="Moneda contable", related="session_id.company_id.currency_id", readonly=True
    )
    company_currency_amount = fields.Monetary(
        string="Equivalente contable", currency_field="company_currency_id", readonly=True
    )
