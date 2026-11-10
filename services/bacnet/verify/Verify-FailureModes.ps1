[CmdletBinding()]
param([string]$LocalIpAddress = '172.21.29.4')
$ErrorActionPreference = 'Stop'
$serviceRoot = Split-Path $PSScriptRoot -Parent
$runtime = Join-Path $serviceRoot '.runtime'
$server = Join-Path $runtime 'server/Northlake.Bacnet.exe'
$probe = Join-Path $runtime 'probe/Northlake.Bacnet.Probe.exe'
$qa = Join-Path $runtime 'failure-check'
$configPath = Join-Path $qa 'bindings.json'
$snapshotPath = Join-Path $qa 'values.json'
$config = Get-Content -LiteralPath (Join-Path $serviceRoot 'bindings.json') -Raw | ConvertFrom-Json
$config.broadcastPort = 47908
for ($i = 0; $i -lt $config.devices.Count; $i++) { $config.devices[$i].unicastPort = 47920 + $i }
if (@(Get-NetUDPEndpoint | Where-Object { $_.LocalPort -in (@(47908) + @($config.devices.unicastPort)) }).Count) {
    throw 'Failure-check UDP ports are occupied.'
}
New-Item -ItemType Directory -Path $qa -Force | Out-Null
$config | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $configPath -Encoding utf8NoBOM
$baseline = Get-Content -LiteralPath (Join-Path $runtime 'state/values.json') -Raw | ConvertFrom-Json
$baseline.configHash = (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash.ToLowerInvariant()

function Save-Snapshot($Snapshot) {
    $Snapshot | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath "$snapshotPath.partial" -Encoding utf8NoBOM
    Move-Item -LiteralPath "$snapshotPath.partial" -Destination $snapshotPath -Force
}

Save-Snapshot $baseline
$process = Start-Process -FilePath $server -ArgumentList @("`"$configPath`"", "`"$qa`"", $LocalIpAddress) -WindowStyle Hidden -RedirectStandardOutput (Join-Path $qa 'server.log') -RedirectStandardError (Join-Path $qa 'server.err.log') -PassThru
$owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($process.Id)"
try {
    Start-Sleep -Seconds 1
    & $probe $configPath $snapshotPath $LocalIpAddress
    if ($LASTEXITCODE -ne 0) { throw 'Isolated protocol control failed.' }

    # Status flags over the wire: one object per non-normal state, then the probe reads every
    # status property and ReadPropertyMultiple back and compares them with this snapshot.
    $flagged = $baseline | ConvertTo-Json -Depth 10 | ConvertFrom-Json
    $flagged.generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('o')
    foreach ($object in $config.devices.objects) {
        $at = [DateTimeOffset]::Parse($flagged.generatedAtUtc).UtcDateTime
        $ticks = [TimeSpan]::FromMinutes($object.intervalMinutes).Ticks
        $flagged.values.($object.valueKey).intervalEndUtc = [DateTime]::new($at.Ticks - ($at.Ticks % $ticks), [DateTimeKind]::Utc).ToString('o')
    }
    $flagged.values.science_chw_tons.status.overridden = $true
    $flagged.values.recreation_chw_ton_hours.status.outOfService = $true
    $psig = $flagged.values.plant_steam_header_psig.status
    $psig.eventState = 'fault'; $psig.reliability = 'no-sensor'; $psig.inAlarm = $true; $psig.fault = $true
    $condensate = $flagged.values.plant_condensate_kgal.status
    $condensate.eventState = 'high-limit'; $condensate.inAlarm = $true
    Save-Snapshot $flagged
    & $probe $configPath $snapshotPath $LocalIpAddress
    if ($LASTEXITCODE -ne 0) { throw 'Status flags were not served as the snapshot states them.' }
    Write-Output 'PASS: overridden, out-of-service, fault and high-limit statuses served by ReadProperty and ReadPropertyMultiple.'
    Save-Snapshot $baseline

    foreach ($case in @('stale', 'future', 'wrong-config', 'wrong-native-end')) {
        $sample = $baseline | ConvertTo-Json -Depth 10 | ConvertFrom-Json
        if ($case -in @('stale', 'future')) {
            $sample.generatedAtUtc = [DateTimeOffset]::UtcNow.AddMinutes($(if ($case -eq 'stale') { -5 } else { 5 })).ToString('o')
            foreach ($object in $config.devices.objects) {
                $at = [DateTimeOffset]::Parse($sample.generatedAtUtc).UtcDateTime
                $ticks = [TimeSpan]::FromMinutes($object.intervalMinutes).Ticks
                $end = [DateTime]::new($at.Ticks - ($at.Ticks % $ticks), [DateTimeKind]::Utc)
                $sample.values.($object.valueKey).intervalEndUtc = $end.ToString('o')
            }
        } elseif ($case -eq 'wrong-config') {
            $sample.configHash = 'different-configuration'
        } else {
            $sample.values.science_chw_ton_hours.intervalEndUtc = [DateTimeOffset]::Parse($sample.values.science_chw_ton_hours.intervalEndUtc).AddMinutes(1).ToString('o')
        }
        Save-Snapshot $sample
        & $probe $configPath $snapshotPath $LocalIpAddress --expect-stale
        if ($LASTEXITCODE -ne 0) { throw "Failed rejection case: $case" }
        Write-Output "PASS: $case rejected by every device."
    }
} finally {
    $current = Get-CimInstance Win32_Process -Filter "ProcessId=$($process.Id)"
    if ($current) {
        if ($current.ExecutablePath -ne $owner.ExecutablePath -or $current.CreationDate -ne $owner.CreationDate) { throw 'Failure-check process ownership changed.' }
        & taskkill /PID $process.Id /T /F | Out-Null
    }
}
