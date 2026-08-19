/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";


function relationId(value) {
    if (!value) {
        return false;
    }

    if (typeof value === "number") {
        return value;
    }

    if (Array.isArray(value)) {
        return value[0] || false;
    }

    return value.id || value.raw?.id || false;
}


patch(OrderSummary.prototype, {
    /**
     * Devuelve los totales en la moneda comercial cuando todas las líneas
     * pertenecen a una única moneda extranjera.
     *
     * En órdenes mixtas conserva el resumen estándar en moneda compañía.
     */
    get multicurrencyTaxTotals() {
        const order = this.currentOrder;
        const standardTotals = order?.taxTotals;

        if (!standardTotals || !order?.lines?.length) {
            return standardTotals;
        }

        const effectiveLines = order.lines.filter(
            (line) =>
                Number(line.qty || 0) !== 0 &&
                !line.combo_parent_id
        );

        if (!effectiveLines.length) {
            return standardTotals;
        }

        const nativeLines = effectiveLines.filter(
            (line) =>
                relationId(line.sale_currency_id) &&
                Number(line.foreign_unit_price || 0) > 0 &&
                Number(line.exchange_rate_snapshot || 0) > 0
        );

        // Hay productos normales CRC mezclados con productos extranjeros.
        if (nativeLines.length !== effectiveLines.length) {
            return standardTotals;
        }

        const currencyIds = new Set(
            nativeLines.map((line) =>
                relationId(line.sale_currency_id)
            )
        );

        // Hay más de una moneda comercial en la misma orden.
        if (currencyIds.size !== 1) {
            return standardTotals;
        }

        const currencyId = [...currencyIds][0];

        /*
         * Usamos un promedio ponderado para contemplar líneas que puedan
         * tener snapshots distintos del tipo de cambio.
         */
        let nativeUntaxedTotal = 0;
        let companyUntaxedTotal = 0;

        for (const line of nativeLines) {
            const nativeSubtotal = Number(
                line.foreign_subtotal || 0
            );

            const rate = Number(
                line.exchange_rate_snapshot || 0
            );

            nativeUntaxedTotal += nativeSubtotal;
            companyUntaxedTotal += nativeSubtotal * rate;
        }

        const effectiveRate =
            nativeUntaxedTotal > 0
                ? companyUntaxedTotal / nativeUntaxedTotal
                : 0;

        if (!(effectiveRate > 0)) {
            return standardTotals;
        }

        return {
            ...standardTotals,

            // Hace que OrderWidget use el símbolo y decimales de USD.
            currency_id: currencyId,

            // Impuesto expresado en moneda comercial.
            tax_amount_currency:
                Number(
                    standardTotals.tax_amount_currency || 0
                ) / effectiveRate,

            // Total con impuestos expresado en moneda comercial.
            order_total:
                Number(
                    standardTotals.order_total || 0
                ) / effectiveRate,
        };
    },
});