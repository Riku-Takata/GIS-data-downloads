param(
    [string]$EnvFile = (Join-Path $PSScriptRoot '.env.mysql')
)

$ErrorActionPreference = 'Stop'
$composeFile = Join-Path $PSScriptRoot 'compose.yaml'
docker compose --env-file $EnvFile -f $composeFile stop
