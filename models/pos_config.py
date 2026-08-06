# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = "pos.config"

    enable_pos_multicurrency = fields.Boolean(
        string="Habilitar multimoneda",
        help="Permite vender productos con precio comercial en otra moneda, recibir efectivo en CRC/USD y escoger la moneda del vuelto.",
    )
    allowed_currency_ids = fields.Many2many(
        "res.currency",
        "pos_config_allowed_currency_rel",
        "config_id",
        "currency_id",
        string="Monedas permitidas",
        domain="[(\"active\", \"=\", True)]",
    )
    default_change_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda predeterminada del vuelto",
    )
    exchange_rate_source = fields.Selection(
        [
            ("odoo", "Tipo de cambio de Odoo"),
            ("manual", "Tipo de cambio manual por sesión"),
        ],
        default="odoo",
        required=True,
        string="Fuente del tipo de cambio",
    )
    manual_usd_crc_rate = fields.Float(
        string="CRC por 1 USD",
        digits=(16, 6),
        help="Solo se usa cuando la fuente seleccionada es manual. Puede actualizarse antes de abrir la sesión.",
    )
    show_dual_currency_totals = fields.Boolean(
        string="Mostrar totales CRC/USD",
        default=True,
    )

    @api.constrains("enable_pos_multicurrency", "allowed_currency_ids", "default_change_currency_id")
    def _check_multicurrency_configuration(self):
        for config in self:
            if not config.enable_pos_multicurrency:
                continue
            if not config.allowed_currency_ids:
                raise ValidationError("Seleccione al menos una moneda permitida para el Punto de Venta.")
            if config.default_change_currency_id and config.default_change_currency_id not in config.allowed_currency_ids:
                raise ValidationError("La moneda predeterminada del vuelto debe estar incluida entre las monedas permitidas.")

    @api.constrains("exchange_rate_source", "manual_usd_crc_rate")
    def _check_manual_rate(self):
        for config in self:
            if config.enable_pos_multicurrency and config.exchange_rate_source == "manual" and config.manual_usd_crc_rate <= 0:
                raise ValidationError("El tipo de cambio manual debe ser mayor que cero.")

    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        for field_name in [
            "enable_pos_multicurrency",
            "allowed_currency_ids",
            "default_change_currency_id",
            "exchange_rate_source",
            "manual_usd_crc_rate",
            "show_dual_currency_totals",
        ]:
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list
