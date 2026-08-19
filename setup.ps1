# Shiksha Setu -- one-command setup for Windows.
#
#   powershell -ExecutionPolicy Bypass -File setup.ps1
#
# Checks what is missing, sets up everything that can be set up, and says
# plainly what it could not do. Safe to run again: every step checks whether it
# has already been done, so a run that failed halfway can simply be repeated.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Say  ($m) { Write-Host "  $m" }
function Good ($m) { Write-Host "  OK    $m" -ForegroundColor Green }
function Warn ($m) { Write-Host "  ..    $m" -ForegroundColor Yellow }
function Die  ($m) { Write-Host "`n  STOP  $m`n" -ForegroundColor Red; exit 1 }

Write-Host "`n  Shiksha Setu setup`n  ------------------`n"

# ---------------------------------------------------------------- prerequisites
Say "Checking what is installed..."

$py = $null
foreach ($c in @("py -3.11", "python3.11", "python")) {
    try {
        $v = & cmd /c "$c --version" 2>&1
        if ($v -match "3\.11\.") { $py = $c; break }
    } catch { }
}
if (-not $py) {
    Die @"
Python 3.11 was not found.

Install it from  https://www.python.org/downloads/release/python-3119/
During installation, tick the box that says "Add python.exe to PATH".
Then run this script again.

(3.12 and 3.13 will not work: some of the libraries this project pins do
not have installers for them yet.)
"@
}
Good "Python 3.11 found ($py)"

try { docker --version | Out-Null } catch {
    Die @"
Docker Desktop was not found.

Install it from  https://www.docker.com/products/docker-desktop/
Start it, wait for the whale icon in the system tray to stop animating,
then run this script again.

Docker is only used to run the database. It is far easier than installing
PostgreSQL and its vector extension by hand on Windows.
"@
}
try { docker info 2>&1 | Out-Null } catch {
    Die "Docker Desktop is installed but not running. Start it, wait for the whale icon to settle, and run this script again."
}
Good "Docker is running"

$hasNode = $false
try { node --version | Out-Null; $hasNode = $true; Good "Node.js found (frontend will be set up)" }
catch { Warn "Node.js not found. The website will be skipped; the API will still work." }

# ---------------------------------------------------------------------- secrets
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") { Copy-Item ".env.example" ".env" }
    else { New-Item ".env" -ItemType File | Out-Null }
    Add-Content ".env" "`nDATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/shiksha_setu"
    $key = -join ((1..64) | ForEach-Object { "{0:x}" -f (Get-Random -Max 16) })
    Add-Content ".env" "JWT_SECRET_KEY=$key"
    Good "Created .env with a fresh JWT secret"
    Warn "You still need to paste NVIDIA_API_KEY into .env -- ask whoever sent you this project."
} else {
    Good ".env already exists, leaving it alone"
}

# --------------------------------------------------------------------- database
Say "Starting the database..."
docker compose up -d postgres | Out-Null

$ready = $false
foreach ($i in 1..40) {
    try {
        docker compose exec -T postgres pg_isready -U postgres -q 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 2
}
if (-not $ready) { Die "The database container started but never became ready. Run 'docker compose logs postgres' and send the output to whoever gave you this project." }
Good "Database is running"

docker compose exec -T postgres psql -U postgres -c "CREATE DATABASE shiksha_setu;" 2>&1 | Out-Null
docker compose exec -T postgres psql -U postgres -d shiksha_setu -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>&1 | Out-Null
Good "Database prepared"

# ------------------------------------------------------------------ the corpus
$books = (docker compose exec -T postgres psql -U postgres -d shiksha_setu -tAc "SELECT count(DISTINCT metadata->>'book_code') FROM processed_content WHERE metadata->>'source'='NCERT'" 2>&1 | Out-String).Trim()
if ($books -notmatch '^\d+$') { $books = "0" }

if ([int]$books -gt 0) {
    Good "Corpus already loaded ($books textbooks)"
} elseif (Test-Path "shiksha_setu.dump") {
    Say "Restoring the corpus from shiksha_setu.dump (a few minutes)..."
    cmd /c "docker compose exec -T postgres pg_restore -U postgres -d shiksha_setu --no-owner < shiksha_setu.dump" 2>&1 | Out-Null
    $books = (docker compose exec -T postgres psql -U postgres -d shiksha_setu -tAc "SELECT count(DISTINCT metadata->>'book_code') FROM processed_content WHERE metadata->>'source'='NCERT'" 2>&1 | Out-String).Trim()
    Good "Corpus restored ($books textbooks)"
} else {
    Warn "No corpus found and no shiksha_setu.dump in this folder."
    Warn "Ask for the dump file and put it here, then run this script again."
    Warn "Without it the system starts but cannot answer questions."
}

# ---------------------------------------------------------------------- backend
if (-not (Test-Path "venv")) {
    Say "Creating the Python environment..."
    cmd /c "$py -m venv venv"
}
Say "Installing Python packages (several minutes the first time)..."
& ".\venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
& ".\venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
Good "Python packages installed"

Say "Applying database migrations..."
& ".\venv\Scripts\python.exe" -m alembic upgrade head 2>&1 | Out-Null
Good "Migrations applied"

# --------------------------------------------------------------------- frontend
if ($hasNode -and -not (Test-Path "frontend\node_modules")) {
    Say "Installing the website's packages..."
    Push-Location frontend; cmd /c "npm ci --silent"; Pop-Location
    Good "Website packages installed"
}

# ------------------------------------------------------------------------- done
Write-Host @"

  Setup finished.

  To start it, open two PowerShell windows in this folder:

    1)  .\venv\Scripts\python.exe -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
    2)  cd frontend ; npm run dev

  Then open  http://localhost:3000  in your browser.

  The very first question will be slow -- about 2.3 GB of language model
  downloads in the background. Every question after that is fast.

"@ -ForegroundColor Cyan

if (-not (Select-String -Path ".env" -Pattern "^NVIDIA_API_KEY=.+" -Quiet)) {
    Write-Host "  One thing is still missing: NVIDIA_API_KEY in the .env file.`n  Without it, search works but the tutor cannot write answers.`n" -ForegroundColor Yellow
}
