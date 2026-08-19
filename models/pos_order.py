# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    change_currency_id = fields.Many2one("res.currency", string="Moneda del vuelto", readonly=True)
    change_amount_currency = fields.Monetary(
        string="Vuelto nativo", currency_field="change_currency_id", readonly=True
    )
    change_amount_company = fields.Monetary(
        string="Vuelto contable", currency_field="currency_id", readonly=True
    )
    change_exchange_rate = fields.Float(string="Tasa del vuelto", digits=(16, 8), readonly=True)


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    sale_currency_id = fields.Many2one("res.currency", string="Moneda comercial", readonly=True)
    foreign_unit_price = fields.Monetary(
        string="Precio unitario nativo", currency_field="sale_currency_id", readonly=True
    )
    foreign_subtotal = fields.Monetary(
        string="Subtotal nativo", currency_field="sale_currency_id", readonly=True
    )
    exchange_rate_snapshot = fields.Float(string="Tipo de cambio", digits=(16, 8), readonly=True)

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        return list(dict.fromkeys(fields_list + [
            "sale_currency_id", "foreign_unit_price", "foreign_subtotal", "exchange_rate_snapshot"
        ]))
