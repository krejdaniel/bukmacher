
$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$Backend = Join-Path $ProjectRoot "backend"
$Frontend = Join-Path $ProjectRoot "frontend"
$Venv = Join-Path $Backend "venv"
$Python = Join-Path $Venv "Scripts\python.exe"

function Write-Step($Message) {
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

try {
    # ---------------------------------------------------------
    # 1. Sprawdzenie wymaganych plikow
    # ---------------------------------------------------------

    Write-Step "Sprawdzanie plikow projektu"

    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw "Nie znaleziono launchera py. Zainstaluj Python 3.13 i zaznacz opcje dodania do PATH."
    }

    if (-not (Test-Path (Join-Path $Backend "requirements.txt"))) {
        throw "Nie znaleziono backend\requirements.txt."
    }

    if (-not (Test-Path (Join-Path $Backend "setup_database.py"))) {
        throw "Nie znaleziono backend\setup_database.py."
    }

    if (-not (Test-Path (Join-Path $Backend "create_tables.py"))) {
        throw "Nie znaleziono backend\create_tables.py."
    }

    if (-not (Test-Path (Join-Path $Frontend "main.py"))) {
        throw "Nie znaleziono frontend\main.py."
    }

    if (-not (Test-Path (Join-Path $ProjectRoot "UruchomFootballPredictor.vbs"))) {
        Write-Host "Uwaga: nie znaleziono UruchomFootballPredictor.vbs w katalogu glownym." -ForegroundColor Yellow
        Write-Host "Instalacja zaleznosci bedzie kontynuowana."
    }

    # ---------------------------------------------------------
    # 2. Utworzenie srodowiska Python
    # ---------------------------------------------------------

    Write-Step "Tworzenie srodowiska Python"

    if (-not (Test-Path $Python)) {
        & py -3.13 -m venv $Venv

        if ($LASTEXITCODE -ne 0) {
            throw "Nie udalo sie utworzyc srodowiska. Sprawdz instalacje Pythona 3.13."
        }
    }
    else {
        Write-Host "Srodowisko backend\venv juz istnieje."
    }

    if (-not (Test-Path $Python)) {
        throw "Nie znaleziono interpretera: $Python"
    }

    # ---------------------------------------------------------
    # 3. Instalacja zaleznosci
    # ---------------------------------------------------------

    Write-Step "Aktualizacja pip"

    & $Python -m pip install --upgrade pip

    if ($LASTEXITCODE -ne 0) {
        throw "Nie udalo sie zaktualizowac pip."
    }

    Write-Step "Instalacja zaleznosci backendu"

    & $Python -m pip install -r (Join-Path $Backend "requirements.txt")

    if ($LASTEXITCODE -ne 0) {
        throw "Instalacja zaleznosci z requirements.txt nie powiodla sie."
    }

    Write-Step "Instalacja interfejsu graficznego"

    & $Python -m pip install PySide6

    if ($LASTEXITCODE -ne 0) {
        throw "Nie udalo sie zainstalowac PySide6."
    }

    # ---------------------------------------------------------
    # 4. Konfiguracja pliku .env
    # ---------------------------------------------------------

    Write-Step "Sprawdzanie konfiguracji"

    $EnvFile = Join-Path $Backend ".env"

    if (-not (Test-Path $EnvFile)) {
        @'
DB_HOST=localhost
DB_PORT=5432
DB_NAME=football_predictor
DB_USER=postgres
DB_PASSWORD=
'@ | Set-Content -Path $EnvFile -Encoding utf8

        Write-Host "Utworzono backend\.env." -ForegroundColor Yellow
        Write-Host "Ustaw lokalne dane PostgreSQL, w tym DB_PASSWORD, przed kontynuacja."
    }
    else {
        Write-Host "Istniejacy backend\.env pozostawiono bez zmian."
    }

    # ---------------------------------------------------------
    # 5. Sprawdzenie PostgreSQL przed tworzeniem bazy
    # ---------------------------------------------------------

    Write-Step "Sprawdzanie uslugi PostgreSQL"

    $PgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue |
        Where-Object { $_.Status -eq "Running" } |
        Select-Object -First 1

    if (-not $PgService) {
        throw "Nie wykryto uruchomionej uslugi PostgreSQL. Zainstaluj PostgreSQL, uruchom usluge i ponownie uruchom instalator."
    }

    Write-Host "Wykryto usluge: $($PgService.Name)" -ForegroundColor Green

    # ---------------------------------------------------------
    # 6. Utworzenie bazy i tabel
    # ---------------------------------------------------------

    Write-Step "Przygotowanie bazy PostgreSQL"

    Push-Location $Backend

    try {
        & $Python ".\setup_database.py"

        if ($LASTEXITCODE -ne 0) {
            throw "Nie udalo sie utworzyc lub sprawdzic bazy PostgreSQL."
        }

        & $Python ".\create_tables.py"

        if ($LASTEXITCODE -ne 0) {
            throw "Nie udalo sie utworzyc tabel."
        }
    }
    finally {
        Pop-Location
    }

    # ---------------------------------------------------------
    # 7. Koniec - bez tworzenia skrotow i dodatkowych VBS
    # ---------------------------------------------------------

    Write-Step "Instalacja zakonczona"

    Write-Host "Zaleznosci zostaly zainstalowane."
    Write-Host "Konfiguracja bazy i tworzenie tabel zostaly wykonane."
    Write-Host "Aplikacje uruchamiaj dotychczasowym plikiem UruchomFootballPredictor.vbs."
}
catch {
    Write-Host "`nBLAD: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Read-Host "`nNacisnij Enter, aby zamknac instalator"
}
