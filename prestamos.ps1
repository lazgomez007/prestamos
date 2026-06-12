<#
.SYNOPSIS
    Calculadora de prestamos: cuota mensual con amortizacion francesa (cuota fija).

.DESCRIPTION
    Define la funcion Get-CuotaMensual, que calcula la cuota mensual de un
    prestamo a partir del capital, la tasa de interes anual y el numero de meses.
#>

function Get-CuotaMensual {
    [CmdletBinding()]
    param(
        # Monto del prestamo.
        [Parameter(Mandatory)][double]$Capital,

        # Tasa de interes anual en decimal (ej. 0.12 = 12%).
        [Parameter(Mandatory)][double]$TasaAnual,

        # Numero de cuotas mensuales.
        [Parameter(Mandatory)][int]$Meses
    )

    if ($Capital -le 0)   { throw "El capital debe ser mayor que cero." }
    if ($Meses -le 0)     { throw "El numero de meses debe ser mayor que cero." }
    if ($TasaAnual -lt 0) { throw "La tasa anual no puede ser negativa." }

    $tasaMensual = $TasaAnual / 12

    if ($tasaMensual -eq 0) {
        # Sin intereses: el capital se reparte en partes iguales.
        $cuota = $Capital / $Meses
    } else {
        $factor = [Math]::Pow(1 + $tasaMensual, $Meses)
        $cuota  = $Capital * ($tasaMensual * $factor) / ($factor - 1)
    }

    return [Math]::Round($cuota, 2)
}
