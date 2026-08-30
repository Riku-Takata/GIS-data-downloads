param(
    [string]$EnvFile = (Join-Path $PSScriptRoot '.env.mysql')
)

$ErrorActionPreference = 'Stop'
$composeFile = Join-Path $PSScriptRoot 'compose.yaml'
$schemaFiles = @(
    (Join-Path $PSScriptRoot 'init\001_schema.sql'),
    (Join-Path $PSScriptRoot 'init\002_japan_boundaries.sql')
)
$dockerDesktop = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'

function Read-EnvFile([string]$Path) {
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
        $name, $value = $trimmed.Split('=', 2)
        $values[$name.Trim()] = $value.Trim()
    }
    return $values
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "MySQL environment file not found: $EnvFile"
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    if (-not (Test-Path -LiteralPath $dockerDesktop)) {
        throw 'Docker Desktop is not installed.'
    }
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
    $ready = $false
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        Start-Sleep -Seconds 3
        docker info *> $null
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            break
        }
    }
    if (-not $ready) { throw 'Docker Desktop did not become ready within 180 seconds.' }
}

docker compose --env-file $EnvFile -f $composeFile up -d
if ($LASTEXITCODE -ne 0) { throw 'docker compose up failed.' }

$healthy = $false
for ($attempt = 1; $attempt -le 60; $attempt++) {
    $health = docker inspect --format '{{.State.Health.Status}}' gsmap-mysql 2>$null
    if ($health -eq 'healthy') {
        $healthy = $true
        break
    }
    Start-Sleep -Seconds 3
}
if (-not $healthy) { throw 'MySQL did not become healthy within 180 seconds.' }

foreach ($schemaFile in $schemaFiles) {
    Get-Content -LiteralPath $schemaFile -Raw |
        docker compose --env-file $EnvFile -f $composeFile exec -T mysql `
            sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"'
    if ($LASTEXITCODE -ne 0) { throw "Applying schema failed: $schemaFile" }
}

$envValues = Read-EnvFile $EnvFile
$readerUser = $envValues['MYSQL_READER_USER']
$readerPassword = $envValues['MYSQL_READER_PASSWORD']
if ($readerUser -notmatch '^[A-Za-z0-9_]+$') {
    throw 'MYSQL_READER_USER may contain only letters, digits, and underscores.'
}
if ($readerPassword -notmatch '^[A-Za-z0-9_.-]{20,}$') {
    throw 'MYSQL_READER_PASSWORD must be at least 20 safe characters.'
}
$readerSql = @"
CREATE USER IF NOT EXISTS '$readerUser'@'%' IDENTIFIED BY '$readerPassword';
ALTER USER '$readerUser'@'%' IDENTIFIED BY '$readerPassword';
GRANT SELECT ON gsmap_japan.* TO '$readerUser'@'%';
FLUSH PRIVILEGES;
"@
$readerSql |
    docker compose --env-file $EnvFile -f $composeFile exec -T mysql `
        sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"'
if ($LASTEXITCODE -ne 0) { throw 'Creating the read-only user failed.' }

docker compose --env-file $EnvFile -f $composeFile ps
