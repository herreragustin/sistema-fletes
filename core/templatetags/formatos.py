from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


@register.filter(name="miles_punto")
def miles_punto(value):
    """
    Formatea importes para visualizacion:
    - 1000 -> 1.000
    - 1250.5 -> 1.250,50
    No modifica el valor original ni la logica numerica.
    """
    if value in (None, ""):
        return "-"

    try:
        numero = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value

    if numero == numero.to_integral_value():
        return f"{int(numero):,}".replace(",", ".")

    texto = f"{numero:,.2f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


@register.filter(name="estado_flete_display")
def estado_flete_display(flete):
    if getattr(flete, "estado", None) == "pendiente":
        return "Reserva"

    get_display = getattr(flete, "get_estado_display", None)
    if callable(get_display):
        return get_display()

    return getattr(flete, "estado", "")
