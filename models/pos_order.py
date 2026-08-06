# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        for field_name in ["change_currency_id", "change_amount_currency", "change_amount_company", "exchange_rate_snapshot"]:
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list

    change_currency_id = fields.Many2one("res.currency", string="Moneda del vuelto", readonly=True)
    change_amount_currency = fields.Monetary(
        string="Vuelto en moneda seleccionada",
        currency_field="change_currency_id",
        readonly=True,
    )
    change_amount_company = fields.Monetary(
        string="Vuelto en moneda compañía",
        currency_field="currency_id",
        readonly=True,
    )
    exchange_rate_snapshot = fields.Float(
        string="Tipo de cambio aplicado",
        digits=(16, 8),
        readonly=True,
    )



class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        for field_name in ["sale_currency_id", "foreign_unit_price", "foreign_subtotal", "exchange_rate_snapshot"]:
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list

    sale_currency_id = fields.Many2one("res.currency", string="Moneda comercial", readonly=True)
    foreign_unit_price = fields.Monetary(
        string="Precio unitario moneda comercial",
        currency_field="sale_currency_id",
        readonly=True,
    )
    foreign_subtotal = fields.Monetary(
        string="Subtotal moneda comercial",
        currency_field="sale_currency_id",
        readonly=True,
    )
    exchange_rate_snapshot = fields.Float(
        string="Tipo de cambio de la línea",
        digits=(16, 8),
        readonly=True,
    )
