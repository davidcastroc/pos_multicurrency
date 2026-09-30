/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";

function relationId(value) {
    if (!value) {
        return false;
    }
    if (typeof value === "number") {
        return value;
    }
    if (Array.isArray(value)) {
        return value[0];
    }
    return value.id || false;
}

function relationIds(value) {
    if (!value) {
        return [];
    }

    if (Array.isArray(value)) {
        return value
            .map((record) => relationId(record))
            .filter(Boolean);
    }

    if (value.records) {
        return value.records
            .map((record) => relationId(record))
            .filter(Boolean);
    }

    return [];
}

patch(ControlButtons.prototype, {
    onClickQuotation() {
        let domain = [
            ["state", "!=", "cancel"],
            ["invoice_status", "!=", "invoiced"],
            ["amount_unpaid", ">", 0],
        ];

        if (this.pos.config.enable_pos_multicurrency) {
            /*
             * POS Multimoneda:
             * permitir cotizaciones en cualquiera de las monedas habilitadas
             * para esta caja, no únicamente en la moneda contable del POS.
             */
            let currencyIds = relationIds(this.pos.config.allowed_currency_ids);

            /*
             * Fallback adicional: obtener monedas desde las listas de precios
             * disponibles si por alguna razón allowed_currency_ids no llegó
             * cargado al frontend.
             */
            if (!currencyIds.length) {
                const pricelists = this.pos.config.available_pricelist_ids || [];

                const records = pricelists.records || pricelists;

                if (Array.isArray(records)) {
                    currencyIds = records
                        .map((pricelist) => relationId(pricelist.currency_id))
                        .filter(Boolean);
                }
            }

            // La moneda principal del POS siempre debe estar permitida.
            const posCurrencyId = relationId(this.pos.currency);
            if (posCurrencyId) {
                currencyIds.push(posCurrencyId);
            }

            currencyIds = [...new Set(currencyIds)];

            if (currencyIds.length) {
                domain.push(["currency_id", "in", currencyIds]);
            } else {
                domain.push(["currency_id", "=", this.pos.currency.id]);
            }
        } else {
            // Comportamiento estándar de Odoo.
            domain.push(["currency_id", "=", this.pos.currency.id]);
        }

        if (this.pos.get_order()?.get_partner()) {
            domain = [
                ...domain,
                [
                    "partner_id",
                    "any",
                    [["id", "child_of", [this.pos.get_order().get_partner().id]]],
                ],
            ];
        }

        this.dialog.add(SelectCreateDialog, {
            resModel: "sale.order",
            noCreate: true,
            multiSelect: false,
            domain,
            onSelected: async (resIds) => {
                await this.pos.onClickSaleOrder(resIds[0]);
            },
        });
    },
});


/*
 * FIX POS SALE -> POS MULTIMONEDA
 *
 * pos_sale carga una sale.order usando directamente:
 *
 *     newLine.set_unit_price(converted_line.price_unit)
 *
 * Para una SO en USD eso significa que $35 termina siendo price_unit=35
 * dentro de un POS cuya moneda contable es CRC.
 *
 * POS Multimoneda mantiene:
 *
 *   foreign_unit_price      -> precio comercial USD
 *   exchange_rate_snapshot  -> CRC por USD
 *   price_unit              -> base contable CRC
 *
 * Después de settleSO restauramos únicamente las líneas provenientes
 * de la sale.order que tengan producto con precio comercial nativo.
 */

import { PosStore } from "@point_of_sale/app/store/pos_store";
import {
    mcProductNativeData,
    mcCompanyPerUnitForProduct,
    mcFindCurrency,
} from "./multicurrency_models";

patch(PosStore.prototype, {
    async settleSO(sale_order, orderFiscalPos) {
        await super.settleSO(...arguments);

        if (!this.config.enable_pos_multicurrency) {
            return;
        }

        const order = this.get_order();
        if (!order) {
            return;
        }

        for (const posLine of order.lines || []) {
            const saleOriginId = relationId(posLine.sale_order_origin_id);

            if (Number(saleOriginId) !== Number(sale_order.id)) {
                continue;
            }

            const product = posLine.product_id;
            const native = mcProductNativeData(product);

            if (
                !native.enabled ||
                !(native.nativePrice > 0) ||
                !native.currencyId
            ) {
                continue;
            }

            /*
             * La SO es la fuente del precio comercial cuando viene desde
             * Ventas. Esto preserva descuentos/precios manuales aplicados
             * específicamente a la cotización.
             */
            const saleLineId = relationId(posLine.sale_order_line_id);

            const saleLine = (sale_order.order_line || []).find(
                (line) => Number(line.id) === Number(saleLineId)
            );

            const nativeUnit = Number(
                saleLine?.price_unit ||
                posLine.foreign_unit_price ||
                native.nativePrice ||
                0
            );

            if (!(nativeUnit > 0)) {
                continue;
            }

            const rate = Number(
                posLine.exchange_rate_snapshot ||
                mcCompanyPerUnitForProduct(product) ||
                0
            );

            if (!(rate > 0)) {
                continue;
            }

            const currency =
                mcFindCurrency(posLine, native.currencyId) ||
                posLine.sale_currency_id ||
                false;

            /*
             * Guardamos nuevamente el contexto comercial nativo que
             * pos_sale pisa al ejecutar set_unit_price(price_unit USD).
             */
            posLine.update({
                sale_currency_id: currency,
                foreign_unit_price: nativeUnit,
                foreign_subtotal:
                    nativeUnit *
                    Number(posLine.qty || 0) *
                    (1 - Number(posLine.discount || 0) / 100),
                exchange_rate_snapshot: rate,
            });

            /*
             * sale.order.line.price_unit conserva la semántica fiscal
             * de la línea de Ventas.
             *
             * Si el impuesto tiene price_include=True, $35 es el precio
             * FINAL con impuesto incluido. Al llevarlo al POS solamente
             * debemos convertir la moneda:
             *
             *     $35 × 450 = ₡15,750
             *
             * El motor fiscal nativo del POS separará posteriormente
             * base e impuesto. No debemos quitar el IVA aquí.
             */
            const companyUnit = nativeUnit * rate;

            if (companyUnit > 0) {
                posLine.set_unit_price(companyUnit);
            }
        }

        /*
         * settleSO ya había recalculado con los valores incorrectos.
         * Recalculamos una vez más después de normalizar las líneas.
         */
        order.recomputeOrderData();
    },
});
