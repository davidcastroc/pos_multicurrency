# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = "pos.config"

    enable_pos_multicurrency = fields.Boolean(string="Habilitar multimoneda")
    allowed_currency_ids = fields.Many2many(
        "res.currency", "pos_config_allowed_currency_rel", "config_id", "currency_id",
        string="Monedas aceptadas", domain=[("active", "=", True)],
    )
    default_change_currency_id = fields.Many2one(
        "res.currency", string="Moneda predeterminada del vuelto", domain=[("active", "=", True)]
    )
    exchange_rate_source = fields.Selection(
        [("odoo", "Tasas de Odoo/BCCR"), ("manual", "Tasas manuales del POS")],
        string="Fuente del tipo de cambio", default="odoo", required=True,
    )
    currency_rate_ids = fields.One2many("pos.config.currency.rate", "config_id", string="Tasas manuales")
    show_native_product_prices = fields.Boolean(string="Mostrar precios nativos", default=True)
    show_company_equivalent = fields.Boolean(string="Mostrar equivalente contable", default=True)

    @api.constrains("enable_pos_multicurrency", "allowed_currency_ids", "default_change_currency_id")
    def _check_multicurrency(self):
        for config in self:
            if not config.enable_pos_multicurrency:
                continue
            if not config.allowed_currency_ids:
                raise ValidationError("Seleccione al menos una moneda aceptada.")
            if config.default_change_currency_id and config.default_change_currency_id not in config.allowed_currency_ids:
                raise ValidationError("La moneda del vuelto debe estar entre las monedas aceptadas.")


class PosConfigCurrencyRate(models.Model):
    _name = "pos.config.currency.rate"
    _description = "Tipo de cambio manual del POS"
    _order = "currency_id"

    config_id = fields.Many2one("pos.config", required=True, ondelete="cascade")
    currency_id = fields.Many2one("res.currency", required=True, domain=[("active", "=", True)])
    company_per_unit = fields.Float(
        string="Moneda compañía por 1 unidad", digits=(16, 8), required=True,
        help="Ejemplo: si la compañía usa CRC y 1 USD equivale a 520 CRC, escriba 520.",
    )
    _sql_constraints = [
        ("config_currency_unique", "unique(config_id, currency_id)", "Solo puede existir una tasa por moneda y POS."),
        ("positive_rate", "check(company_per_unit > 0)", "El tipo de cambio debe ser mayor que cero."),
    ]
