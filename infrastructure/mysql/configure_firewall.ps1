param(
    [string]$LanSubnet = '192.168.11.0/24'
)

$ErrorActionPreference = 'Stop'
$principal = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from PowerShell opened with "Run as administrator".'
}

$rules = @(
    @{ Name = 'GSMaP MySQL LAN'; Port = 3306 },
    @{ Name = 'GSMaP Adminer LAN'; Port = 8081 }
)

foreach ($rule in $rules) {
    Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue |
        Remove-NetFirewallRule
    New-NetFirewallRule `
        -DisplayName $rule.Name `
        -Description "GSMaP database access from trusted private LAN only" `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $rule.Port `
        -Profile Private `
        -RemoteAddress $LanSubnet | Out-Null
}

Get-NetFirewallRule -DisplayName ($rules.Name) |
    Select-Object DisplayName, Enabled, Profile, Direction, Action
