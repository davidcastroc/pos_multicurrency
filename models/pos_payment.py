# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosPayment(models.Model):
    _inherit = "pos.payment"

    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        for field_name in ["payment_currency_id", "amount_currency", "exchange_rate_snapshot"]:
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list

    payment_currency_id = fields.Many2one("res.currency", string="Moneda recibida", readonly=True)
    amount_currency = fields.Monetary(
        string="Importe en moneda recibida",
        currency_field="payment_currency_id",
        readonly=True,
    )
    exchange_rate_snapshot = fields.Float(
        string="Tipo de cambio aplicado",
        digits=(16, 8),
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        payments = super().create(vals_list)
        payments.mapped("session_id")._rebuild_currency_summaries()
        return payments

    def unlink(self):
        sessions = self.mapped("session_id")
        result = super().unlink()
        sessions._rebuild_currency_summaries()
        return result
