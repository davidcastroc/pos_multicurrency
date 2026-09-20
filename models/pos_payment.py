# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosPayment(models.Model):
    _inherit = "pos.payment"

    payment_currency_id = fields.Many2one("res.currency", string="Moneda recibida", readonly=True)
    amount_currency = fields.Monetary(string="Importe recibido nativo", currency_field="payment_currency_id", readonly=True)
    exchange_rate_snapshot = fields.Float(string="Tipo de cambio", digits=(16, 8), readonly=True)
    exchange_rate_role = fields.Selection([("same", "Misma moneda"), ("buy", "Compra"), ("sell", "Venta"), ("generic", "General")], string="Rol de tasa", readonly=True)

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        return list(dict.fromkeys(fields_list + ["id", "uuid", "pos_order_id", "payment_method_id", "amount", "payment_date", "is_change", "payment_status", "card_type", "card_brand", "card_no", "cardholder_name", "payment_ref_no", "payment_method_authcode", "payment_method_issuer_bank", "payment_method_payment_mode", "transaction_id", "ticket", "payment_currency_id", "amount_currency", "exchange_rate_snapshot", "exchange_rate_role"]))
