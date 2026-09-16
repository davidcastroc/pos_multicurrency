# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosPayment(models.Model):
    _inherit = "pos.payment"

    payment_currency_id = fields.Many2one("res.currency", string="Moneda recibida", readonly=True)
    amount_currency = fields.Monetary(string="Importe recibido nativo", currency_field="payment_currency_id", readonly=True)
    exchange_rate_snapshot = fields.Float(string="Tipo de cambio", digits=(16, 8), readonly=True)

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        return list(dict.fromkeys(fields_list + ["payment_currency_id", "amount_currency", "exchange_rate_snapshot"]))
