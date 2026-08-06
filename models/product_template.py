# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    pos_sale_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda de venta en POS",
        default=lambda self: self.env.company.currency_id,
        help="Moneda comercial en la que se captura y muestra el precio del producto en Punto de Venta. "
             "El inventario y la valoración contable continúan en la moneda de la compañía.",
    )
    pos_foreign_price = fields.Monetary(
        string="Precio POS en moneda comercial",
        currency_field="pos_sale_currency_id",
        help="Precio que verá el cajero para este producto. En productos en CRC puede dejarse en cero y se usará el precio de venta normal.",
    )
    pos_use_foreign_currency = fields.Boolean(
        string="Precio multimoneda en POS",
        compute="_compute_pos_use_foreign_currency",
        store=True,
    )
    pos_company_price_preview = fields.Monetary(
        string="Equivalente estimado en moneda compañía",
        currency_field="currency_id",
        compute="_compute_pos_company_price_preview",
        help="Vista previa usando el tipo de cambio vigente. El importe definitivo se congela al crear la línea de venta.",
    )

    @api.depends("pos_sale_currency_id", "company_id.currency_id")
    def _compute_pos_use_foreign_currency(self):
        for product in self:
            company = product.company_id or self.env.company
            product.pos_use_foreign_currency = bool(
                product.pos_sale_currency_id
                and product.pos_sale_currency_id != company.currency_id
            )

    @api.depends("pos_foreign_price", "pos_sale_currency_id", "company_id", "company_id.currency_id")
    def _compute_pos_company_price_preview(self):
        today = fields.Date.context_today(self)
        for product in self:
            company = product.company_id or self.env.company
            if product.pos_use_foreign_currency and product.pos_foreign_price:
                product.pos_company_price_preview = product.pos_sale_currency_id._convert(
                    product.pos_foreign_price,
                    company.currency_id,
                    company,
                    today,
                    round=False,
                )
            else:
                product.pos_company_price_preview = product.list_price

    @api.constrains("pos_foreign_price", "pos_sale_currency_id")
    def _check_pos_foreign_price(self):
        for product in self:
            if product.pos_use_foreign_currency and product.pos_foreign_price <= 0:
                raise ValidationError("Indique un precio mayor que cero para el producto configurado en moneda extranjera.")


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        for field_name in [
            "pos_sale_currency_id",
            "pos_foreign_price",
            "pos_use_foreign_currency",
            "pos_company_price_preview",
        ]:
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list
