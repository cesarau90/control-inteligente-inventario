param([switch]$Monitor)

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectDir

$venvPython = Join-Path $projectDir '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $venvPython) {
    if ($Monitor) {
        & $venvPython monitor.py
    } else {
        & $venvPython app.py
    }
    exit $LASTEXITCODE
}

# Opción de demostración para este equipo, donde Python viene con pgAdmin.
$pgPython = 'C:\Program Files\PostgreSQL\18\pgAdmin 4\python\python.exe'
$localDeps = Join-Path $projectDir '.deps'
if ((Test-Path -LiteralPath $pgPython) -and (Test-Path -LiteralPath $localDeps)) {
    if ($Monitor) {
        $code = "import sys,runpy;sys.path[:0]=[r'$projectDir',r'$localDeps'];runpy.run_path('monitor.py',run_name='__main__')"
    } else {
        $code = "import sys;sys.path[:0]=[r'$projectDir',r'$localDeps'];from app import app;app.run(host='127.0.0.1',port=5000,debug=False)"
    }
    & $pgPython -c $code
    exit $LASTEXITCODE
}

Write-Error 'No se encontró Python preparado. Instala Python y sigue los pasos de README.md.'
exit 1
