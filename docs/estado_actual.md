# Estado actual del proyecto

## Estado general

El proyecto se encuentra funcional y usable para operacion diaria en entorno local.
Quedo preparado para comenzar carga de datos reales luego de limpiar la base demo.

Base tecnica actual:
- Django
- SQLite
- entorno virtual local
- Git y GitHub configurados
- trabajo posible entre PC y notebook usando el mismo repo

## Modulos existentes

- Clientes
- Choferes
- Fletes
- Facturacion
- Cuenta corriente de clientes
- Liquidacion de choferes
- Reportes
- Importadores DBF aislados

## Funcionalidades implementadas

### Operacion
- alta y edicion de clientes
- alta y edicion de choferes
- alta y edicion de fletes
- generacion de reservas recurrentes semanales y mensuales desde nuevo flete
- filtros en listados
- listado de Fletes con informacion operativa ampliada:
  - horarios reales
  - duracion
  - estado de cobro
  - fecha de cobro
- estados de flete:
  - pendiente, mostrado al usuario como Reserva
  - en_curso
  - finalizado
  - cancelado

### Tiempos del flete
- guarda inicio real al pasar a `en_curso`
- guarda finalizacion real al pasar a `finalizado`
- calcula duracion
- permite cargar manualmente hora de comienzo y finalizacion cuando un flete se registra despues de haber sido realizado
- los fletes en curso ya muestran la hora de inicio real en los listados operativos

### Cobro a clientes
- facturacion basada en fletes finalizados
- efectivo se cobra automaticamente
- cuenta corriente queda pendiente de cobro

### Cuenta corriente
- solo incluye viajes con `forma_de_pago = cuenta_corriente`
- resumen por cliente
- detalle por cliente
- ficha de cliente con historial operativo
- filtros por periodo
- cierre simple de cobranza
- indicadores visuales de cierre disponible

### Liquidacion de choferes
- tipo de liquidacion por chofer:
  - semanal
  - quincenal
  - mensual
- porcentaje de liquidacion por chofer
- importe del chofer calculado dinamicamente
- ficha de chofer con historial operativo
- cierre simple de liquidacion
- fallback al ultimo periodo con movimientos
- indicadores visuales de cierre disponible

### Home
- redisenada como panel operativo diario
- muestra fletes del dia con datos operativos completos
- muestra reservas futuras de los proximos 7 dias por separado
- los fletes en curso muestran hora de inicio real
- mantiene accesos rapidos utiles
- la version anterior quedo respaldada en `core/templates/core/panel_inicio_anterior.html`

### Reportes
- totales por periodo
- cobrado / pendiente cliente
- pagado / pendiente chofer
- resultado estimado general

## Partes mas consolidadas

- flujo operativo de fletes
- cuenta corriente de clientes
- liquidacion de choferes
- cierres simples
- navegacion principal
- backup previo a limpieza de datos demo

## Partes pendientes o mejorables

- reportes mas detallados por cliente y chofer
- exportaciones
- validaciones adicionales
- cierres mas formales o historicos
- mejoras administrativas y de UX fina
