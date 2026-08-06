# -*- coding: utf-8 -*-
from collections import defaultdict
from odoo import api, fields, models


class PosSession(models.Model):
    _inherit = "pos.session"

    currency_summary_ids = fields.One2many(
        "pos.session.currency.summary",
        "session_id",
        string="Resumen por moneda",
        readonly=True,
    )

    @api.model
    def get_multicurrency_bootstrap(self, config_id):
        config = self.env["pos.config"].browse(config_id).exists()
        company_currency = config.company_id.currency_id
        currencies = config.allowed_currency_ids | company_currency
        today = fields.Date.context_today(self)
        result = []
        for currency in currencies:
            if currency == company_currency:
                company_per_unit = 1.0
            elif (
                config.exchange_rate_source == "manual"
                and currency.name == "USD"
                and company_currency.name == "CRC"
            ):
                company_per_unit = config.manual_usd_crc_rate
            else:
                company_per_unit = currency._convert(
                    1.0,
                    company_currency,
                    config.company_id,
                    today,
                    round=False,
                )
            result.append({
                "id": currency.id,
                "name": currency.name,
                "symbol": currency.symbol,
                "position": currency.position,
                "decimal_places": currency.decimal_places,
                "company_per_unit": company_per_unit,
                "is_company_currency": currency == company_currency,
            })
        return {
            "enabled": config.enable_pos_multicurrency,
            "company_currency_id": company_currency.id,
            "default_change_currency_id": config.default_change_currency_id.id or company_currency.id,
            "currencies": result,
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
                ("is_change", "=", False),
            ])
            for payment in payments:
                currency = payment.payment_currency_id or session.company_id.currency_id
                foreign_amount = payment.amount_currency if payment.payment_currency_id else payment.amount
                totals[currency.id]["received"] += foreign_amount
                totals[currency.id]["company"] += payment.amount

            orders = self.env["pos.order"].sudo().search([
                ("session_id", "=", session.id),
                ("state", "not in", ["draft", "cancel"]),
                ("change_currency_id", "!=", False),
            ])
            for order in orders:
                totals[order.change_currency_id.id]["change"] += order.change_amount_currency
                totals[order.change_currency_id.id]["company"] -= order.change_amount_company

            Summary.search([("session_id", "=", session.id)]).unlink()
            Summary.create([
                {
                    "session_id": session.id,
                    "currency_id": currency_id,
                    "amount_received": values["received"],
                    "change_given": values["change"],
                    "net_amount": values["received"] - values["change"],
                    "company_currency_amount": values["company"],
                }
                for currency_id, values in totals.items()
            ])


class PosSessionCurrencySummary(models.Model):
    _name = "pos.session.currency.summary"
    _description = "Resumen de moneda de sesión POS"
    _order = "currency_id"

    session_id = fields.Many2one("pos.session", required=True, ondelete="cascade", index=True)
    currency_id = fields.Many2one("res.currency", required=True, readonly=True)
    amount_received = fields.Monetary(string="Recibido", currency_field="currency_id", readonly=True)
    change_given = fields.Monetary(string="Vuelto entregado", currency_field="currency_id", readonly=True)
    net_amount = fields.Monetary(string="Neto esperado", currency_field="currency_id", readonly=True)
    company_currency_amount = fields.Monetary(
        string="Equivalente moneda compañía",
        currency_field="company_currency_id",
        readonly=True,
    )
    company_currency_id = fields.Many2one(related="session_id.company_id.currency_id", readonly=True)
