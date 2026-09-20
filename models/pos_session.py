# -*- coding: utf-8 -*-
from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PosSession(models.Model):
    _inherit = "pos.session"

    currency_balance_ids = fields.One2many(
        "pos.session.currency.balance", "session_id", string="Caja por moneda", copy=False
    )
    currency_summary_ids = fields.One2many(
        "pos.session.currency.summary", "session_id", string="Arqueo por moneda", readonly=True
    )

    def _mc_rate(self, currency, at_date=None):
        self.ensure_one()
        company_currency = self.company_id.currency_id
        if currency == company_currency:
            return 1.0
        config = self.config_id
        config._ensure_exchange_rates(silent=True, force=False)
        if company_currency.name == "CRC" and currency.name == "USD" and config.mc_usd_sell_rate > 0:
            return config.mc_usd_sell_rate
        if config.exchange_rate_source == "manual":
            line = config.currency_rate_ids.filtered(lambda r: r.currency_id == currency)[:1]
            if not line:
                raise UserError(_("Falta la tasa manual para %s.") % currency.display_name)
            return line.company_per_unit
        return currency._convert(1.0, company_currency, self.company_id, at_date or fields.Date.context_today(self), round=False)

    def _mc_ensure_balances(self):
        Balance = self.env["pos.session.currency.balance"].sudo()
        for session in self:
            currencies = session.config_id.allowed_currency_ids | session.company_id.currency_id
            existing = session.currency_balance_ids.mapped("currency_id")
            vals = []
            for currency in currencies - existing:
                vals.append({
                    "session_id": session.id,
                    "currency_id": currency.id,
                    "opening_exchange_rate": session._mc_rate(currency),
                })
            if vals:
                Balance.create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        sessions = super().create(vals_list)
        sessions._mc_ensure_balances()
        return sessions

    @api.model
    def get_multicurrency_bootstrap(self, config_id):
        config = self.env["pos.config"].browse(config_id).exists()
        if not config:
            raise UserError(_("No se encontró la configuración del Punto de Venta."))

        config._ensure_exchange_rates(silent=True, force=False)
        company = config.company_id
        company_currency = company.currency_id
        currencies = config.allowed_currency_ids | company_currency
        manual = {line.currency_id.id: line for line in config.currency_rate_ids}
        date = fields.Date.context_today(self)
        values = []

        for currency in currencies:
            if currency == company_currency:
                generic = buy = sell = 1.0
            elif company_currency.name == "CRC" and currency.name == "USD" and config.mc_usd_buy_rate > 0 and config.mc_usd_sell_rate > 0:
                generic = config.mc_usd_sell_rate
                buy = config.mc_usd_buy_rate
                sell = config.mc_usd_sell_rate
            elif config.exchange_rate_source == "manual":
                line = manual.get(currency.id)
                if not line:
                    raise UserError(_("Falta la tasa manual para %s.") % currency.display_name)
                generic = line.company_per_unit
                buy = line.company_per_unit_buy or generic
                sell = line.company_per_unit_sell or generic
            else:
                generic = currency._convert(1.0, company_currency, company, date, round=False)
                buy = sell = generic

            values.append({
                "id": currency.id,
                "name": currency.name,
                "symbol": currency.symbol,
                "position": currency.position,
                "decimal_places": currency.decimal_places,
                "company_per_unit": generic,
                "buy_company_per_unit": buy,
                "sell_company_per_unit": sell,
                "is_company_currency": currency == company_currency,
            })

        return {
            "enabled": config.enable_pos_multicurrency,
            "company_currency_id": company_currency.id,
            "default_change_currency_id": config.default_change_currency_id.id or company_currency.id,
            "show_native_product_prices": config.show_native_product_prices,
            "show_company_equivalent": config.show_company_equivalent,
            "rate_source": config.mc_rate_source_label or config.exchange_rate_source,
            "rate_date": config.mc_rate_date.isoformat() if config.mc_rate_date else False,
            "usd_buy_rate": config.mc_usd_buy_rate,
            "usd_sell_rate": config.mc_usd_sell_rate,
            "currencies": values,
        }

    @api.model
    def mc_get_session_cash_state(self, session_id):
        session = self.browse(session_id).exists()
        if not session:
            raise UserError(_("La sesión POS no existe."))
        session._mc_ensure_balances()
        session._rebuild_currency_summaries()
        result = []
        for bal in session.currency_balance_ids.sorted(lambda x: (x.currency_id.name, x.id)):
            summary = session.currency_summary_ids.filtered(lambda x: x.currency_id == bal.currency_id)[:1]
            cash_payments = self.env["pos.payment"].sudo().search([
                ("session_id", "=", session.id),
                ("pos_order_id.state", "not in", ["draft", "cancel"]),
                ("payment_method_id.is_cash_count", "=", True),
            ])
            cash_received = 0.0
            for payment in cash_payments:
                pay_currency = payment.payment_currency_id or session.company_id.currency_id
                if pay_currency == bal.currency_id:
                    cash_received += payment.amount_currency if payment.payment_currency_id else payment.amount
            # Odoo persists change as a negative pos.payment line. Therefore
            # cash_received is already NET of change and must not subtract it again.
            # We keep cash_change only as an informational breakdown for the UI.
            change_orders = self.env["pos.order"].sudo().search([
                ("session_id", "=", session.id), ("state", "not in", ["draft", "cancel"]),
                ("change_currency_id", "=", bal.currency_id.id),
            ])
            cash_change = sum(change_orders.mapped("change_amount_currency"))
            expected = bal.opening_amount + cash_received + bal.cash_in_amount - bal.cash_out_amount
            method_rows = []
            methods = session.config_id.payment_method_ids.filtered(
                lambda method: (method.payment_currency_id or session.company_id.currency_id) == bal.currency_id
            )
            all_payments = self.env["pos.payment"].sudo().search([
                ("session_id", "=", session.id),
                ("pos_order_id.state", "not in", ["draft", "cancel"]),
                ("payment_method_id", "in", methods.ids),
            ])
            for method in methods.sorted(lambda m: (m.sequence if "sequence" in m._fields else 0, m.id)):
                method_payments = all_payments.filtered(lambda p: p.payment_method_id == method)
                native_total = sum(
                    p.amount_currency if p.payment_currency_id else p.amount
                    for p in method_payments
                )
                method_rows.append({
                    "id": method.id,
                    "name": method.name,
                    "is_cash": bool(method.is_cash_count),
                    "amount": native_total,
                })

            result.append({
                "balance_id": bal.id,
                "currency_id": bal.currency_id.id,
                "name": bal.currency_id.name,
                "symbol": bal.currency_id.symbol,
                "position": bal.currency_id.position,
                "decimal_places": bal.currency_id.decimal_places,
                "opening_amount": bal.opening_amount,
                "opening_rate": bal.opening_exchange_rate,
                "received": cash_received,
                "change": cash_change,
                "cash_in": bal.cash_in_amount,
                "cash_out": bal.cash_out_amount,
                "expected": expected,
                "counted": bal.closing_counted_amount,
                "difference": bal.closing_counted_amount - expected if bal.closing_counted else 0.0,
                "methods": method_rows,
                "rate_source": session.config_id.mc_rate_source_label or session.config_id.exchange_rate_source,
                "rate_date": session.config_id.mc_rate_date.isoformat() if session.config_id.mc_rate_date else False,
                "usd_buy_rate": session.config_id.mc_usd_buy_rate,
                "usd_sell_rate": session.config_id.mc_usd_sell_rate,
            })
        return result

    @api.model
    def mc_set_opening_balances(self, session_id, amounts):
        session = self.browse(session_id).exists()
        if not session:
            raise UserError(_("La sesión POS no existe."))
        session._mc_ensure_balances()
        for item in amounts or []:
            bal = session.currency_balance_ids.filtered(lambda b: b.currency_id.id == int(item.get("currency_id", 0)))[:1]
            if bal:
                amount = float(item.get("amount") or 0.0)
                if amount < 0:
                    raise ValidationError(_("El saldo inicial no puede ser negativo."))
                bal.write({"opening_amount": amount, "opening_exchange_rate": session._mc_rate(bal.currency_id)})
        return session.mc_get_session_cash_state(session.id)

    @api.model
    def mc_set_closing_counts(self, session_id, amounts):
        session = self.browse(session_id).exists()
        if not session:
            raise UserError(_("La sesión POS no existe."))
        session._mc_ensure_balances()
        for item in amounts or []:
            bal = session.currency_balance_ids.filtered(lambda b: b.currency_id.id == int(item.get("currency_id", 0)))[:1]
            if bal:
                amount = float(item.get("amount") or 0.0)
                if amount < 0:
                    raise ValidationError(_("El conteo final no puede ser negativo."))
                bal.write({
                    "closing_counted_amount": amount,
                    "closing_counted": True,
                    "closing_exchange_rate": session._mc_rate(bal.currency_id),
                })
        return session.mc_get_session_cash_state(session.id)

    @api.model
    def mc_cash_move(self, session_id, currency_id, amount, direction="in", note=None):
        session = self.browse(session_id).exists()
        currency = self.env["res.currency"].browse(currency_id).exists()
        if not session or not currency:
            raise UserError(_("Sesión o moneda inválida."))
        if currency not in (session.config_id.allowed_currency_ids | session.company_id.currency_id):
            raise ValidationError(_("La moneda no está habilitada en este POS."))
        amount = float(amount or 0.0)
        if amount <= 0:
            raise ValidationError(_("El monto debe ser mayor que cero."))
        session._mc_ensure_balances()
        bal = session.currency_balance_ids.filtered(lambda b: b.currency_id == currency)[:1]
        vals = {"cash_in_amount": bal.cash_in_amount + amount} if direction == "in" else {"cash_out_amount": bal.cash_out_amount + amount}
        bal.write(vals)
        self.env["pos.session.currency.cash.move"].sudo().create({
            "session_id": session.id, "currency_id": currency.id, "direction": direction,
            "amount": amount, "exchange_rate_snapshot": session._mc_rate(currency), "note": note or "",
        })
        return session.mc_get_session_cash_state(session.id)

    def action_refresh_currency_summary(self):
        self._rebuild_currency_summaries()
        return True

    def _rebuild_currency_summaries(self):
        Summary = self.env["pos.session.currency.summary"].sudo()
        for session in self:
            totals = defaultdict(lambda: {"received": 0.0, "change": 0.0, "company": 0.0})
            payments = self.env["pos.payment"].sudo().search([
                ("session_id", "=", session.id), ("pos_order_id.state", "not in", ["draft", "cancel"]),
            ])
            for payment in payments:
                currency = payment.payment_currency_id or session.company_id.currency_id
                native = payment.amount_currency if payment.payment_currency_id else payment.amount
                totals[currency.id]["received"] += native
                totals[currency.id]["company"] += payment.amount
            orders = self.env["pos.order"].sudo().search([
                ("session_id", "=", session.id), ("state", "not in", ["draft", "cancel"]), ("change_currency_id", "!=", False),
            ])
            for order in orders:
                totals[order.change_currency_id.id]["change"] += order.change_amount_currency
                totals[order.change_currency_id.id]["company"] -= order.change_amount_company
            Summary.search([("session_id", "=", session.id)]).unlink()
            vals = []
            for currency in (session.config_id.allowed_currency_ids | session.company_id.currency_id):
                data = totals[currency.id]
                vals.append({
                    "session_id": session.id, "currency_id": currency.id,
                    "amount_received": data["received"], "change_given": data["change"],
                    "net_amount": data["received"] - data["change"], "company_currency_amount": data["company"],
                })
            if vals:
                Summary.create(vals)


class PosSessionCurrencyBalance(models.Model):
    _name = "pos.session.currency.balance"
    _description = "Caja POS por moneda"
    _order = "currency_id"

    session_id = fields.Many2one("pos.session", required=True, ondelete="cascade", index=True)
    currency_id = fields.Many2one("res.currency", required=True, readonly=True)
    opening_amount = fields.Monetary(currency_field="currency_id", string="Apertura", default=0.0)
    opening_exchange_rate = fields.Float(string="Tasa apertura", digits=(16, 8), default=1.0)
    cash_in_amount = fields.Monetary(currency_field="currency_id", string="Entradas", default=0.0)
    cash_out_amount = fields.Monetary(currency_field="currency_id", string="Salidas", default=0.0)
    closing_counted_amount = fields.Monetary(currency_field="currency_id", string="Contado al cierre", default=0.0)
    closing_counted = fields.Boolean(default=False)
    closing_exchange_rate = fields.Float(string="Tasa cierre", digits=(16, 8), default=1.0)
    _sql_constraints = [("session_currency_unique", "unique(session_id,currency_id)", "Solo puede existir un arqueo por moneda y sesión.")]


class PosSessionCurrencyCashMove(models.Model):
    _name = "pos.session.currency.cash.move"
    _description = "Movimiento de efectivo POS por moneda"
    _order = "create_date desc, id desc"

    session_id = fields.Many2one("pos.session", required=True, ondelete="cascade", index=True)
    currency_id = fields.Many2one("res.currency", required=True)
    direction = fields.Selection([("in", "Entrada"), ("out", "Salida")], required=True)
    amount = fields.Monetary(currency_field="currency_id", required=True)
    exchange_rate_snapshot = fields.Float(digits=(16, 8), required=True)
    note = fields.Char()
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)


class PosSessionCurrencySummary(models.Model):
    _name = "pos.session.currency.summary"
    _description = "Arqueo por moneda de sesión POS"
    _order = "currency_id"

    session_id = fields.Many2one("pos.session", required=True, ondelete="cascade", index=True)
    currency_id = fields.Many2one("res.currency", string="Moneda física", required=True, readonly=True)
    amount_received = fields.Monetary(string="Recibido", currency_field="currency_id", readonly=True)
    change_given = fields.Monetary(string="Vuelto", currency_field="currency_id", readonly=True)
    net_amount = fields.Monetary(string="Neto esperado", currency_field="currency_id", readonly=True)
    company_currency_id = fields.Many2one("res.currency", related="session_id.company_id.currency_id", readonly=True)
    company_currency_amount = fields.Monetary(string="Equivalente contable", currency_field="company_currency_id", readonly=True)
