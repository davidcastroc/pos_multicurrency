# -*- coding: utf-8 -*-
from odoo import fields, models


class PosPayment(models.Model):
    _inherit = "pos.payment"

    payment_currency_id = fields.Many2one("res.currency", string="Moneda recibida", readonly=True)
    amount_currency = fields.Monetary(
        string="Importe recibido nativo", currency_field="payment_currency_id", readonly=True
    )
    exchange_rate_snapshot = fields.Float(string="Tipo de cambio", digits=(16, 8), readonly=True)
