
$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$Backend = Join-Path $ProjectRoot "backend"
$Frontend = Join-Path $ProjectRoot "frontend"
$Venv = Join-Path $Backend "venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$BackupFile = Join-Path $ProjectRoot "football_predictor.backup"

function Write-Step($Message) {
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

function Get-EnvValue($Name, $Default = "") {
    $EnvFile = Join-Path $Backend ".env"

    if (Test-Path $EnvFile) {
        $Line = Get-Content $EnvFile |
            Where-Object { $_ -match "^\s*$([regex]::Escape($Name))\s*=" } |
            Select-Object -Last 1

        if ($Line) {
            $Value = ($Line -split "=", 2)[1].Trim()

            if ($Value.Length -ge 2) {
                if (
                    ($Value.StartsWith('"') -and $Value.EndsWith('"')) -or
                    ($Value.StartsWith("'") -and $Value.EndsWith("'"))
                ) {
                    $Value = $Value.Substring(1, $Value.Length - 2)
                }
            }

            return $Value
        }
    }

    return $Default
}

try {
    # ---------------------------------------------------------
    # 1. Sprawdzenie plikow projektu i Pythona
    # ---------------------------------------------------------

    Write-Step "Sprawdzanie plikow projektu"

    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw "Nie znaleziono launchera py. Zainstaluj Python 3.13 i zaznacz opcje dodania do PATH."
    }

    $RequiredFiles = @(
        (Join-Path $Backend "requirements.txt"),
        (Join-Path $Backend "setup_database.py"),
        (Join-Path $Backend "create_tables.py"),
        (Join-Path $Frontend "main.py")
    )

    foreach ($File in $RequiredFiles) {
        if (-not (Test-Path $File)) {
            throw "Nie znaleziono wymaganego pliku: $File"
        }
    }

    if (-not (Test-Path (Join-Path $ProjectRoot "UruchomFootballPredictor.vbs"))) {
        Write-Host "Uwaga: nie znaleziono UruchomFootballPredictor.vbs." -ForegroundColor Yellow
    }

    if (Test-Path $BackupFile) {
        Write-Host "Znaleziono kopie bazy: $BackupFile" -ForegroundColor Green
    }
    else {
        Write-Host "Nie znaleziono football_predictor.backup. Instalacja przygotuje pusta baze." -ForegroundColor Yellow
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

    Write-Step "Instalacja przegladarki Chromium dla Playwright"

    & $Python -m playwright install chromium

    if ($LASTEXITCODE -ne 0) {
        throw "Nie udalo sie pobrac przegladarki Chromium wymaganej przez Playwright."
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

        Write-Host "Utworzono backend\.env."
    }
    else {
        Write-Host "Istniejacy backend\.env pozostawiono bez zmian."
    }

    # ---------------------------------------------------------
    # 5. Wykrycie PostgreSQL
    # ---------------------------------------------------------

    Write-Step "Sprawdzanie PostgreSQL"

    $PgServices = @(
        Get-Service -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Name -like "*postgres*" -or
                $_.DisplayName -like "*postgres*"
            }
    )

    $PgService = $PgServices |
        Where-Object { $_.Status -eq "Running" } |
        Select-Object -First 1

    if (-not $PgService) {
        Write-Host ""
        Write-Host "Nie wykryto uruchomionego PostgreSQL." -ForegroundColor Yellow
        Write-Host "Otwieram oficjalna strone pobierania PostgreSQL dla Windows."
        Write-Host ""
        Write-Host "Zainstaluj PostgreSQL i zapamietaj haslo uzytkownika postgres."

        Start-Process "https://www.postgresql.org/download/windows/"

        Read-Host "Po zainstalowaniu PostgreSQL nacisnij Enter"

        $PgServices = @(
            Get-Service -ErrorAction SilentlyContinue |
                Where-Object {
                    $_.Name -like "*postgres*" -or
                    $_.DisplayName -like "*postgres*"
                }
        )

        $PgService = $PgServices |
            Where-Object { $_.Status -eq "Running" } |
            Select-Object -First 1

        if (-not $PgService) {
            $StoppedService = $PgServices | Select-Object -First 1

            if ($StoppedService) {
                Write-Host "Proba uruchomienia uslugi: $($StoppedService.Name)"

                try {
                    Start-Service -Name $StoppedService.Name
                    Start-Sleep -Seconds 3
                    $PgService = Get-Service -Name $StoppedService.Name
                }
                catch {
                    throw "Nie udalo sie uruchomic uslugi PostgreSQL. Uruchom ja recznie i ponownie uruchom instalator."
                }
            }
        }

        if (-not $PgService -or $PgService.Status -ne "Running") {
            throw "Nie wykryto dzialajacej uslugi PostgreSQL. Sprawdz, czy instalacja zostala zakonczona."
        }
    }

    Write-Host "PostgreSQL dziala: $($PgService.Name)" -ForegroundColor Green

    # ---------------------------------------------------------
    # 6. Przygotowanie bazy i tabel
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
    # 7. Przywracanie danych z kopii
    # ---------------------------------------------------------

    if (Test-Path $BackupFile) {
        Write-Step "Przywracanie bazy z kopii zapasowej"

        Write-Host ""
        Write-Host "UWAGA: przywracanie moze zastapic tabele i dane w bazie docelowej!" -ForegroundColor Yellow
        Write-Host "Plik kopii: $BackupFile"
        Write-Host "Baza docelowa: $(Get-EnvValue 'DB_NAME' 'football_predictor')"
        Write-Host ""

        $Confirmation = Read-Host "Aby przywrocic kopie i zastapic istniejace obiekty, wpisz TAK"

        if ($Confirmation -ceq "TAK") {
            $PgBin = "C:\Program Files\PostgreSQL"

            $PgRestoreCandidates = @()

            if (Test-Path $PgBin) {
                $PgRestoreCandidates = @(
                    Get-ChildItem $PgBin -Filter pg_restore.exe -Recurse -ErrorAction SilentlyContinue |
                        Where-Object { $_.Directory.Name -eq "bin" }
                )
            }

            if ($PgRestoreCandidates.Count -eq 0) {
                throw "Nie znaleziono pg_restore.exe. Sprawdz instalacje PostgreSQL."
            }

            $PgRestore = $PgRestoreCandidates |
				Sort-Object {
					$VersionText = $_.Directory.Parent.Name -replace '[^0-9].*$', ''
					[int]$VersionText
				} -Descending |
				Select-Object -First 1 -ExpandProperty FullName

            $DbHost = Get-EnvValue "DB_HOST" "localhost"
            $DbPort = Get-EnvValue "DB_PORT" "5432"
            $DbName = Get-EnvValue "DB_NAME" "football_predictor"
            $DbUser = Get-EnvValue "DB_USER" "postgres"
            $DbPassword = Get-EnvValue "DB_PASSWORD" ""

            # Najpierw sprawdzamy, czy plik jest poprawna kopia pg_dump.
            & $PgRestore --list $BackupFile | Out-Null

            if ($LASTEXITCODE -ne 0) {
                throw "Plik football_predictor.backup jest nieprawidlowy lub nie mozna go odczytac."
            }

            # Jesli haslo jest zapisane w .env, uzyj go bez umieszczania
            # hasla w argumentach procesu. Jesli nie, pg_restore zapyta o haslo.
            $PreviousPgPassword = $env:PGPASSWORD
            $HadPgPassword = Test-Path Env:PGPASSWORD

            try {
                if (-not [string]::IsNullOrEmpty($DbPassword)) {
                    $env:PGPASSWORD = $DbPassword
                }
                else {
                    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
                }

                $RestoreArgs = @(
                    "--host=$DbHost",
                    "--port=$DbPort",
                    "--username=$DbUser",
                    "--dbname=$DbName",
                    "--clean",
                    "--if-exists",
                    "--no-owner",
                    "--no-privileges",
                    "--exit-on-error",
                    $BackupFile
                )

                & $PgRestore @RestoreArgs

                if ($LASTEXITCODE -ne 0) {
                    throw "Przywracanie bazy nie powiodlo sie. Sprawdz haslo, wersje PostgreSQL i komunikaty powyzej."
                }
            }
            finally {
                if ($HadPgPassword) {
                    $env:PGPASSWORD = $PreviousPgPassword
                }
                else {
                    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
                }
            }

            Write-Host "Dane z kopii zostaly przywrocone." -ForegroundColor Green
        }
        else {
            Write-Host "Pominieto przywracanie kopii. Baza pozostaje bez importu danych." -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "Pominieto import: brak football_predictor.backup."
    }

    # ---------------------------------------------------------
    # 8. Zakonczenie
    # ---------------------------------------------------------

    Write-Step "Instalacja zakonczona"

    Write-Host "Zaleznosci Pythona zostaly zainstalowane." -ForegroundColor Green
    Write-Host "Baza danych i tabele zostaly przygotowane." -ForegroundColor Green
    Write-Host ""
    Write-Host "Aplikacje uruchamiaj plikiem UruchomFootballPredictor.vbs."
    Write-Host "Nie utworzono skrotow ani dodatkowych plikow uruchamiajacych."
}
catch {
    Write-Host "`nBLAD: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Read-Host "`nNacisnij Enter, aby zamknac instalator"
}
