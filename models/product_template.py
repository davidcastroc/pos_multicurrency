# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    pos_sale_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Moneda comercial en POS",
        default=lambda self: self.env.company.currency_id,
        domain=[("active", "=", True)],
        help=(
            "Moneda que verá el cajero y el cliente. "
            "La contabilidad permanece en la moneda de la compañía."
        ),
    )

    pos_foreign_price = fields.Monetary(
        string="Precio comercial POS",
        currency_field="pos_sale_currency_id",
        help="Precio nativo del producto en la moneda seleccionada.",
    )

    pos_use_foreign_currency = fields.Boolean(
        string="Precio extranjero",
        compute="_compute_pos_use_foreign_currency",
        store=True,
    )

    pos_company_price_preview = fields.Monetary(
        string="Equivalente contable estimado",
        currency_field="currency_id",
        compute="_compute_pos_company_price_preview",
    )

    @api.depends(
        "pos_sale_currency_id",
        "company_id",
        "company_id.currency_id",
    )
    def _compute_pos_use_foreign_currency(self):
        for product in self:
            company = product.company_id or self.env.company

            product.pos_use_foreign_currency = bool(
                product.pos_sale_currency_id
                and product.pos_sale_currency_id != company.currency_id
            )

    @api.depends(
        "pos_foreign_price",
        "pos_sale_currency_id",
        "pos_use_foreign_currency",
        "list_price",
        "company_id",
        "company_id.currency_id",
    )
    def _compute_pos_company_price_preview(self):
        conversion_date = fields.Date.context_today(self)

        for product in self:
            company = product.company_id or self.env.company

            if (
                product.pos_use_foreign_currency
                and product.pos_sale_currency_id
                and product.pos_foreign_price > 0
            ):
                product.pos_company_price_preview = (
                    product.pos_sale_currency_id._convert(
                        product.pos_foreign_price,
                        company.currency_id,
                        company,
                        conversion_date,
                        round=False,
                    )
                )
            else:
                product.pos_company_price_preview = product.list_price

    @api.constrains(
        "pos_sale_currency_id",
        "pos_foreign_price",
    )
    def _check_pos_foreign_price(self):
        for product in self:
            if (
                product.pos_use_foreign_currency
                and product.pos_foreign_price <= 0
            ):
                raise ValidationError(
                    "El precio comercial en moneda extranjera "
                    "debe ser mayor que cero."
                )


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _load_pos_data_fields(self, config_id):
        """
        Conserva todos los campos estándar y los agregados por otros módulos,
        incluyendo CABYS, impuestos y facturación electrónica.
        """
        fields_list = super()._load_pos_data_fields(config_id)

        custom_fields = [
            "pos_sale_currency_id",
            "pos_foreign_price",
            "pos_use_foreign_currency",
            "pos_company_price_preview",
        ]

        return list(dict.fromkeys(fields_list + custom_fields))