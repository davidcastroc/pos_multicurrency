# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    payment_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda recibida",
        help="Moneda física o bancaria recibida por este método. Si se deja vacía se usa la moneda de la compañía.",
    )
    is_foreign_cash = fields.Boolean(
        string="Efectivo en moneda extranjera",
        help="Actívelo únicamente cuando este método representa efectivo físico en otra moneda.",
    )
    allow_change_in_currency = fields.Boolean(
        string="Permitir dar vuelto en esta moneda",
        default=False,
    )

    @api.constrains("is_foreign_cash", "payment_currency_id")
    def _check_foreign_cash_currency(self):
        for method in self:
            if method.is_foreign_cash and not method.payment_currency_id:
                raise ValidationError("Seleccione la moneda recibida para el método de efectivo extranjero.")

    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        for field_name in ["payment_currency_id", "is_foreign_cash", "allow_change_in_currency"]:
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list
