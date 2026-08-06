# La Leona | POS Multimoneda — Odoo 18

Primer entregable funcional para operar un Punto de Venta cuya moneda contable es CRC, con tours comercializados en USD, pagos mixtos y vuelto seleccionable en CRC o USD.

## Decisión funcional

El inventario **no cambia de moneda**. Las existencias, costos y valoración permanecen en la moneda de la compañía. En el producto se agrega una **moneda comercial de POS** y un **precio comercial**; al agregarlo a la orden, el POS congela el equivalente en CRC y el tipo de cambio utilizado.

## Incluye

- Precio de productos normales en CRC.
- Precio comercial de tours en USD.
- Conversión a moneda de la compañía al crear la línea.
- Método de pago asociado explícitamente a una moneda; no depende del nombre "USD".
- Captura del monto físico recibido en USD y equivalente contable en CRC.
- Selección de moneda del vuelto antes de validar.
- Registro de moneda, monto original y tipo de cambio en orden, líneas y pagos.
- Resumen de sesión por moneda: recibido, vuelto entregado, neto esperado y equivalente en CRC.
- Fuente de cambio desde Odoo/BCCR existente o tasa manual de la sesión.
- Interfaz integrada visualmente con Odoo 18 y adaptable a tablet/móvil.

## Configuración

1. Instalar el módulo `la_leona_pos_multicurrency`.
2. Verificar que CRC sea la moneda de la compañía y que USD esté activa.
3. En Punto de Venta > Configuración, activar **Habilitar multimoneda** y seleccionar CRC/USD.
4. Crear métodos separados, por ejemplo:
   - Efectivo CRC: moneda CRC.
   - Efectivo USD: moneda USD, efectivo extranjero y permite vuelto.
   - Tarjeta CRC/USD según el flujo bancario real.
5. En cada tour, activar la moneda USD e indicar el precio comercial.
6. Los productos regulares se mantienen con su precio normal en CRC.
7. Abrir una sesión nueva después de cualquier cambio de configuración o tasa.

## Pruebas de aceptación sugeridas

- Producto CRC ₡10.000, pago CRC ₡20.000, vuelto CRC ₡10.000.
- Tour USD $50 con tasa 520, pago $50, sin vuelto.
- Venta mixta CRC + USD, pago combinado con ambos métodos.
- Tour $50, cliente entrega $60, vuelto seleccionado USD $10.
- Tour $50, cliente entrega $60, vuelto seleccionado CRC ₡5.200.
- Cierre de sesión mostrando recibido y neto esperado separados para CRC y USD.
- Facturación de una venta mixta conservando importes contables en CRC.

## Nota técnica importante

Este entregable está construido contra la arquitectura de modelos reactivos y `pos.load.mixin` de Odoo 18. Antes de producción debe instalarse en una rama de pruebas de Odoo.sh y ejecutar la matriz anterior con la localización y el módulo BCCR de La Leona, especialmente para validar redondeos y el asiento de cierre.
