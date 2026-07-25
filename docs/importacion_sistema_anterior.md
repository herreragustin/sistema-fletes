# Importacion del sistema anterior

## Ruta utilizada

La carpeta elegida para la importacion historica fue:

`C:\Users\Agustin\Desktop\ViejosAUTODATA\AUTODATA`

## Comando utilizado

Primero se valido con `dry-run`:

`python manage.py importar_sistema_anterior "C:\Users\Agustin\Desktop\ViejosAUTODATA\AUTODATA" --dry-run`

Luego se realizo la importacion real:

`python manage.py importar_sistema_anterior "C:\Users\Agustin\Desktop\ViejosAUTODATA\AUTODATA" --replace`

## Conteos finales importados

- clientes historicos: 1066
- choferes historicos: 36
- viajes historicos: 7990
- reservas historicas: 14337
- omitidos: 1
- errores: 0

## Observaciones sobre el parser

Durante la validacion previa se detecto que muchos viajes y reservas quedaban sin origen o destino porque el parser tomaba el primer alias encontrado aunque viniera vacio.

Se corrigio la resolucion de aliases para que:
- ignore `None`
- ignore strings vacios
- ignore strings con solo espacios
- siga probando aliases hasta encontrar el primer valor util

Tambien se agrego `HASTAORI` como alias posible de destino.

## Resultado de la correccion de aliases

Antes de la correccion:
- viajes sin origen: 5924
- viajes sin destino: 5924
- reservas sin origen: 14248
- reservas sin destino: 14309

Despues de la correccion:
- viajes sin origen: 55
- viajes sin destino: 46
- reservas sin origen: 0
- reservas sin destino: 0

## Aclaracion importante

La informacion importada del sistema anterior es solo consulta.

No se mezcla con:
- clientes operativos
- choferes operativos
- fletes operativos
- facturacion actual
- cuenta corriente actual
- liquidacion actual
