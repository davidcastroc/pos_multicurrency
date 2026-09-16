# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    mc_kind = fields.Selection([
        ("other", "Otro"), ("cash_crc", "Efectivo CRC"), ("cash_usd", "Efectivo USD"),
        ("sinpe", "SINPE Móvil"), ("card_crc", "Tarjeta CRC"), ("card_usd", "Tarjeta USD"),
        ("transfer_crc", "Transferencia CRC"), ("transfer_usd", "Transferencia USD"),
    ], default="other", required=True, string="Tipo multimoneda")
    payment_currency_id = fields.Many2one(
        "res.currency", string="Moneda recibida", domain=[("active", "=", True)],
        help="Moneda física/bancaria recibida. El diario contable puede permanecer en moneda compañía.",
    )
    allow_change_in_currency = fields.Boolean(string="Permitir vuelto en esta moneda", default=True)

    @api.constrains("payment_currency_id", "is_cash_count")
    def _check_payment_currency(self):
        for method in self:
            if method.payment_currency_id and not method.payment_currency_id.active:
                raise ValidationError("La moneda del método de pago debe estar activa.")

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        return list(dict.fromkeys(fields_list + ["mc_kind", "payment_currency_id", "allow_change_in_currency"]))
