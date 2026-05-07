# Handoff del proyecto

## Estado general

Proyecto Django de gestion de fletes ya funcional en entorno local Windows.

Base actual:
- Django
- SQLite
- entorno virtual local
- Git inicializado localmente

## Funcionalidades ya implementadas

### Operacion principal
- alta y edicion de clientes
- alta y edicion de choferes
- alta y edicion de fletes
- listado de fletes
- filtros en fletes
- cambio de estados de flete:
  - pendiente
  - en_curso
  - finalizado
  - cancelado

### Tiempos del flete
- guarda fecha/hora al pasar a `en_curso`
- guarda fecha/hora al pasar a `finalizado`
- calcula duracion del viaje

### Cobro a clientes
- facturacion basada en fletes finalizados
- forma de pago:
  - efectivo
  - cuenta_corriente
- si el flete es efectivo:
  - queda cobrado automaticamente al finalizar
- si el flete es cuenta corriente:
  - queda pendiente de cobro

### Cuenta corriente de clientes
- solo muestra fletes con `forma_de_pago = cuenta_corriente`
- resumen por cliente
- detalle por cliente
- filtros por periodo
- cierre simple de cobranza por periodo
- marca como cobrados todos los pendientes visibles del cliente

### Pago a choferes
- liquidacion separada del cobro a clientes
- estados de pago al chofer
- fecha de pago al chofer
- tipo de liquidacion por chofer:
  - semanal
  - quincenal
  - mensual
- porcentaje de liquidacion por chofer:
  - default 60
  - configurable por chofer
- `importe_chofer` calculado dinamicamente desde el porcentaje
- cierre simple de liquidacion por periodo
- fallback al ultimo periodo con movimientos si el actual no tiene viajes

### Reportes
- reportes por periodo
- total facturado
- total cobrado
- total pendiente de cobro
- total a pagar a choferes
- total pagado a choferes
- total pendiente a choferes
- resultado estimado

### Visual / usabilidad
- home simple
- filtros con submit automatico en varios listados
- importes formateados con separador de miles
- resaltado de excepciones en porcentaje de liquidacion de choferes
- indicadores visuales de cierre disponible en cuenta corriente y liquidacion

## Reglas de negocio ya definidas

### Clientes
- la cuenta corriente incluye solo viajes de `cuenta_corriente`
- efectivo no entra en cuenta corriente

### Choferes
- cada chofer tiene:
  - `tipo_liquidacion`
  - `porcentaje_liquidacion`
- `importe_chofer` no usa mas un 60% fijo global
- el pago al chofer es independiente del cobro al cliente

## Decisiones importantes tomadas

- no usar observaciones en la UI salvo pedido explicito
- no mezclar liquidacion de choferes con cobranza de clientes
- mantener logica simple y operativa, sin contabilidad compleja
- `db.sqlite3` queda fuera de Git
- la importacion DBF quedo aislada y no participa del flujo principal

## Git

Repositorio Git local inicializado.

Primer commit creado:

`Estado base funcional del sistema de fletes`

Archivos importantes agregados:
- `.gitignore`
- `README_GIT.md`

## Archivos de referencia utiles

- `core/models.py`
- `core/views.py`
- `core/forms.py`
- `core/urls.py`
- `core/templates/core/`
- `README_GIT.md`

## Pendientes recomendados

Opciones razonables para seguir:

1. mejorar reportes por cliente y por chofer
2. mejorar cierres y resumenes operativos
3. validar con el cliente si el porcentaje de chofer puede variar por tipo de viaje
4. seguir puliendo UX y navegacion

## Proximo paso recomendado

Seguir con reportes o con consolidacion de reglas reales del negocio, segun lo que defina el cliente.

Si hay dudas sobre como se liquida realmente a un chofer en casos especiales, conviene validar eso antes de seguir agregando complejidad.
