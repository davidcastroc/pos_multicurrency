# -*- coding: utf-8 -*-

from odoo import api, models


class ResCurrency(models.Model):
    _inherit = "res.currency"

    @api.model
    def _load_pos_data_domain(self, data):
        """
        Carga en el frontend todas las monedas necesarias para el flujo
        multimoneda, no únicamente la moneda principal del POS.
        """
        pos_config_data = data.get("pos.config", {}).get("data", [])

        if not pos_config_data:
            return super()._load_pos_data_domain(data)

        config_id = pos_config_data[0].get("id")

        if not config_id:
            return super()._load_pos_data_domain(data)

        config = self.env["pos.config"].browse(config_id).exists()

        if not config:
            return super()._load_pos_data_domain(data)

        currencies = self.env["res.currency"]

        # Moneda de la compañía.
        currencies |= config.company_id.currency_id

        # Moneda principal del Punto de Venta.
        if "currency_id" in config._fields:
            currencies |= config.currency_id

        # Monedas permitidas en el POS multimoneda.
        if "allowed_currency_ids" in config._fields:
            currencies |= config.allowed_currency_ids

        # Moneda predeterminada para el vuelto.
        if "default_change_currency_id" in config._fields:
            currencies |= config.default_change_currency_id

        # Monedas configuradas en los métodos de pago.
        payment_methods = config.payment_method_ids

        if (
            payment_methods
            and "payment_currency_id"
            in payment_methods._fields
        ):
            currencies |= payment_methods.mapped(
                "payment_currency_id"
            )

        # Monedas configuradas en tasas manuales.
        if "currency_rate_ids" in config._fields:
            currencies |= config.currency_rate_ids.mapped(
                "currency_id"
            )

        # Monedas utilizadas por productos disponibles en POS.
        product_currencies = (
            self.env["product.template"]
            .search(
                [
                    ("available_in_pos", "=", True),
                    ("pos_sale_currency_id", "!=", False),
                ]
            )
            .mapped("pos_sale_currency_id")
        )

        currencies |= product_currencies

        return [("id", "in", currencies.ids)]