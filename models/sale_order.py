# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _mc_get_commercial_currency(self):
        """
        Devuelve la moneda comercial de los productos que ya están
        presentes en la cotización.

        Si hay productos comerciales en distintas monedas, se bloquea
        la mezcla porque una sale.order de Odoo tiene una única moneda.
        """
        self.ensure_one()

        currencies = self.order_line.filtered(
            lambda line:
                not line.display_type
                and line.product_id
                and line.product_id.product_tmpl_id.pos_use_foreign_currency
                and line.product_id.product_tmpl_id.pos_sale_currency_id
                and line.product_id.product_tmpl_id.pos_foreign_price > 0
        ).mapped(
            "product_id.product_tmpl_id.pos_sale_currency_id"
        )

        if len(currencies) > 1:
            raise ValidationError(
                "No se pueden mezclar productos con precios comerciales "
                "en distintas monedas dentro de la misma cotización."
            )

        return currencies[:1]

    def _mc_get_pricelist_for_currency(self, currency):
        self.ensure_one()

        if not currency:
            return self.env["product.pricelist"]

        return self.env["product.pricelist"].search(
            [
                ("currency_id", "=", currency.id),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", self.company_id.id),
            ],
            limit=1,
        )

    def _mc_sync_currency_from_product(self, product):
        """
        Hace que la cotización adopte la moneda comercial del producto.
        """
        self.ensure_one()

        template = product.product_tmpl_id

        if not (
            template.pos_use_foreign_currency
            and template.pos_sale_currency_id
            and template.pos_foreign_price > 0
        ):
            return

        target_currency = template.pos_sale_currency_id

        existing_currencies = self.order_line.filtered(
            lambda line:
                not line.display_type
                and line.product_id
                and line.product_id != product
                and line.product_id.product_tmpl_id.pos_use_foreign_currency
                and line.product_id.product_tmpl_id.pos_sale_currency_id
                and line.product_id.product_tmpl_id.pos_foreign_price > 0
        ).mapped(
            "product_id.product_tmpl_id.pos_sale_currency_id"
        )

        incompatible = existing_currencies.filtered(
            lambda currency: currency != target_currency
        )

        if incompatible:
            raise ValidationError(
                "No se pueden mezclar productos con precios comerciales "
                "en distintas monedas dentro de la misma cotización.\n\n"
                f"El producto seleccionado utiliza {target_currency.name}."
            )

        pricelist = self._mc_get_pricelist_for_currency(target_currency)

        if not pricelist:
            raise ValidationError(
                f"No existe una tarifa de venta en {target_currency.name}.\n\n"
                "Cree una tarifa para esta moneda antes de utilizar "
                "productos con precio comercial en ella."
            )

        # Al asignar la tarifa correcta, Odoo calcula currency_id
        # utilizando la moneda de esa tarifa.
        self.pricelist_id = pricelist
        self.currency_id = target_currency

    @api.depends("partner_id", "company_id", "order_line.product_id")
    def _compute_pricelist_id(self):
        """
        Conserva el comportamiento estándar para cotizaciones normales.

        Cuando existen productos con precio comercial nativo,
        su moneda tiene prioridad sobre la tarifa predeterminada
        del cliente.
        """
        super()._compute_pricelist_id()

        for order in self:
            if order.state != "draft":
                continue

            commercial_currency = order._mc_get_commercial_currency()

            if not commercial_currency:
                continue

            pricelist = order._mc_get_pricelist_for_currency(
                commercial_currency
            )

            if not pricelist:
                raise ValidationError(
                    f"No existe una tarifa de venta en "
                    f"{commercial_currency.name}."
                )

            order.pricelist_id = pricelist

    @api.depends("pricelist_id", "company_id", "order_line.product_id")
    def _compute_currency_id(self):
        """
        La moneda comercial de los productos tiene prioridad.
        Si no hay productos multimoneda, se usa el comportamiento
        estándar de Odoo.
        """
        super()._compute_currency_id()

        for order in self:
            if order.state != "draft":
                continue

            commercial_currency = order._mc_get_commercial_currency()

            if commercial_currency:
                order.currency_id = commercial_currency


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.onchange("product_id")
    def _onchange_mc_product_currency(self):
        for line in self:
            if not line.product_id or not line.order_id:
                continue

            line.order_id._mc_sync_currency_from_product(
                line.product_id
            )

    def _mc_native_product_price(self):
        self.ensure_one()

        if not self.product_id:
            return False

        template = self.product_id.product_tmpl_id

        if not (
            template.pos_use_foreign_currency
            and template.pos_sale_currency_id
            and template.pos_foreign_price > 0
        ):
            return False

        if (
            template.pos_sale_currency_id
            != self.order_id.currency_id
        ):
            return False

        return template.pos_foreign_price

    def _reset_price_unit(self):
        """
        Usa el precio comercial nativo cuando la moneda de la
        cotización coincide con la moneda comercial del producto.

        Para productos normales conserva íntegramente el
        comportamiento estándar de Odoo.
        """
        native_lines = self.filtered(
            lambda line:
                line._mc_native_product_price() is not False
        )

        standard_lines = self - native_lines

        if standard_lines:
            super(
                SaleOrderLine,
                standard_lines,
            )._reset_price_unit()

        for line in native_lines:
            line = line.with_company(line.company_id)

            native_price = line._mc_native_product_price()

            product_taxes = (
                line.product_id.taxes_id
                ._filter_taxes_by_company(line.company_id)
            )

            price_unit = (
                line.product_id
                ._get_tax_included_unit_price_from_price(
                    native_price,
                    product_taxes=product_taxes,
                    fiscal_position=line.order_id.fiscal_position_id,
                )
            )

            line.update({
                "price_unit": price_unit,
                "technical_price_unit": price_unit,
            })
