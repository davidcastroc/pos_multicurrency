# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    change_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda del vuelto",
        readonly=True,
    )

    change_amount_currency = fields.Monetary(
        string="Vuelto nativo",
        currency_field="change_currency_id",
        readonly=True,
    )

    change_amount_company = fields.Monetary(
        string="Vuelto contable",
        currency_field="currency_id",
        readonly=True,
    )

    change_exchange_rate = fields.Float(
        string="Tasa del vuelto",
        digits=(16, 8),
        readonly=True,
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)

        extra_fields = [
            # Campos base necesarios por el frontend del POS
            "id",
            "uuid",
            "name",
            "session_id",
            "user_id",
            "company_id",
            "currency_id",
            "partner_id",
            "state",
            "date_order",

            # IMPORTANTES:
            # Odoo usa estos campos para construir tracking_number.
            # Sin sequence_number puede terminar mostrando "NaN"
            # en el encabezado del recibo.
            "sequence_number",
            "tracking_number",

            # Líneas y pagos
            "lines",
            "payment_ids",

            # Totales contables
            "amount_total",
            "amount_tax",
            "amount_paid",
            "amount_return",

            # Configuración de la orden
            "fiscal_position_id",
            "pricelist_id",
            "to_invoice",
            "general_note",

            # Multimoneda - vuelto
            "change_currency_id",
            "change_amount_currency",
            "change_amount_company",
            "change_exchange_rate",
        ]

        # Evita campos duplicados si alguno ya viene de super().
        return list(dict.fromkeys(fields_list + extra_fields))


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    sale_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda comercial",
        readonly=True,
    )

    foreign_unit_price = fields.Monetary(
        string="Precio unitario nativo",
        currency_field="sale_currency_id",
        readonly=True,
    )

    foreign_subtotal = fields.Monetary(
        string="Subtotal nativo",
        currency_field="sale_currency_id",
        readonly=True,
    )

    exchange_rate_snapshot = fields.Float(
        string="Tipo de cambio",
        digits=(16, 8),
        readonly=True,
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)

        extra_fields = [
            "sale_currency_id",
            "foreign_unit_price",
            "foreign_subtotal",
            "exchange_rate_snapshot",
        ]

        return list(dict.fromkeys(fields_list + extra_fields))