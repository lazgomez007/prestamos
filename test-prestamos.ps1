# Pruebas de la calculadora de prestamos.
# Ejecutar con:  powershell -File .\test-prestamos.ps1

. "$PSScriptRoot\prestamos.ps1"

$script:fallos = 0

function Assert-Equal {
    param($Esperado, $Real, [string]$Nombre)

    if ([Math]::Abs($Esperado - $Real) -lt 0.01) {
        Write-Host "  OK    - $Nombre" -ForegroundColor Green
    } else {
        Write-Host "  FALLO - $Nombre (esperado $Esperado, obtenido $Real)" -ForegroundColor Red
        $script:fallos++
    }
}

Write-Host "Ejecutando pruebas..."

# Prestamo de 12000 al 12% anual a 12 meses.
Assert-Equal 1066.19 (Get-CuotaMensual -Capital 12000 -TasaAnual 0.12 -Meses 12) "Cuota con interes (12000, 12%, 12 meses)"

if ($script:fallos -eq 0) {
    Write-Host "`nTodas las pruebas pasaron." -ForegroundColor Green
    exit 0
} else {
    Write-Host "`n$($script:fallos) prueba(s) fallaron." -ForegroundColor Red
    exit 1
}
