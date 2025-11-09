# Bot de Gestión Financiera

Este bot permite gestionar finanzas, inventario y realizar operaciones monetarias en diferentes cajas (CFG, SC, TRD).

## Comandos Principales

### Comandos Básicos

| Tarea | Comando | Propósito |
|-------|---------|-----------|
| Inicio | `/start` | Obtener la lista básica de comandos |
| Balance | `/balance` | Ver los saldos actuales de todas las cajas (CFG, SC, TRD) |

### Gestión de Dinero

| Tarea | Comando | Propósito |
|-------|---------|-----------|
| Ingreso | `/ingreso 100 usd cfg` | Registrar entrada de 100 USD a la Caja CFG |
| Gasto | `/gasto 5000 cup sc pago de renta de oficina` | Registrar salida de 5000 CUP de la Caja SC |
| Conversión | `/cambio 20 usd-cup trd a cfg` | Vender 20 USD de TRD y recibir 8200 CUP (asumiendo 410 CUP/USD) en CFG |

### Gestión de Inventario

| Tarea | Comando | Propósito |
|-------|---------|-----------|
| Ver Stock | `/stock` | Revisar el inventario actual de productos |
| Comprar Stock | `/entrada SHIRT01 5 100 usd cfg 'Compra lote 5'` | Añadir 5 unidades de SHIRT01 (registra GASTO de 100 USD) |
| Vender Producto | `/venta SHIRT01 1 30 usd sc 'Vendido a cliente A'` | Registrar INGRESO de 30 USD y restar 1 unidad del stock |

## Notas Importantes

- Las cajas disponibles son: CFG, SC y TRD
- Los montos deben especificarse con la moneda (USD o CUP)
- Para las operaciones de compra y venta de stock, es necesario especificar el código del producto
- Las descripciones en las operaciones deben ir entre comillas simples
