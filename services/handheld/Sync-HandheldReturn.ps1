param(
    [Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{32}$')][string]$Round,
    [Parameter(Mandatory)][string]$Target,
    [Parameter(Mandatory)][string]$TargetsFile,
    [Parameter(Mandatory)][string]$GatewayRoot,
    [string]$Url = 'http://host.docker.internal:18082',
    [string]$Image = 'hippo-northlake-handheld:local',
    [switch]$Replay
)
$ErrorActionPreference = 'Stop'
$configPath = (Resolve-Path -LiteralPath $TargetsFile).Path
$rootPath = (Resolve-Path -LiteralPath $GatewayRoot).Path
if (-not (Test-Path -LiteralPath $rootPath -PathType Container)) { throw 'GatewayRoot must be an existing gateway workspace directory.' }
$config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json -AsHashtable
if (-not $config.ContainsKey($Target) -or $config[$Target].destination -ne '/delivery-root/Input') {
    throw 'The selected target must name /delivery-root/Input inside the helper container.'
}
$dockerArgs = @('run', '--rm', '--mount', "type=bind,source=$rootPath,target=/delivery-root",
    '--mount', "type=bind,source=$configPath,target=/targets.json,readonly", $Image,
    'sync', '--url', $Url, '--round', $Round, '--target', $Target, '--targets', '/targets.json')
if ($Replay) { $dockerArgs += '--replay' }
& docker @dockerArgs
if ($LASTEXITCODE -ne 0) { throw "Handheld synchronization failed (exit $LASTEXITCODE). Inspect the receipt ledger before retrying." }
