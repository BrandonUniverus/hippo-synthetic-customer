[CmdletBinding()]
param(
    [ValidateSet('Setup', 'Start', 'Stop', 'Status', 'Verify')]
    [string]$Action = 'Status',
    [string]$LocalIpAddress = '172.21.29.4',
    [string]$Python = 'python',
    [string]$EnergyHippoRoot = 'C:\Hippo\Git\univerus\energyhippo',
    [string]$ArtifactsPath = ''
)

$ErrorActionPreference = 'Stop'
$sourceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$runtime = Join-Path $PSScriptRoot '.runtime'
$state = Join-Path $runtime 'state'
$config = Join-Path $PSScriptRoot 'bindings.json'
$processFile = Join-Path $runtime 'processes.json'
$producerPython = Join-Path $runtime 'venv/Scripts/python.exe'
$serverExe = Join-Path $runtime 'server/Northlake.Bacnet.exe'
$probeExe = Join-Path $runtime 'probe/Northlake.Bacnet.Probe.exe'
if (!$ArtifactsPath) { $ArtifactsPath = Join-Path $runtime 'build' }

function Get-OwnedProcess($Entry) {
    if (!$Entry -or !$Entry.Id) { return $null }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($Entry.Id)"
    if (!$process) { return $null }
    if ($process.ExecutablePath -ne $Entry.ExecutablePath -or
        $process.CreationDate.ToUniversalTime().Ticks.ToString() -ne $Entry.CreationTicks) {
        throw "PID $($Entry.Id) no longer belongs to this source. Reconcile $processFile."
    }
    return $process
}

function Save-ProcessEntry($Process, $Role, $Record) {
    $details = Get-CimInstance Win32_Process -Filter "ProcessId=$($Process.Id)"
    if (!$details) { throw "$Role exited during startup. Inspect $runtime/$Role.err.log." }
    $Record[$Role] = @{
        Id = $details.ProcessId
        ExecutablePath = $details.ExecutablePath
        CreationTicks = $details.CreationDate.ToUniversalTime().Ticks.ToString()
    }
    $Record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath "$processFile.partial" -Encoding utf8
    Move-Item -LiteralPath "$processFile.partial" -Destination $processFile -Force
}

function Stop-OwnedProcesses($Record) {
    foreach ($role in @('server', 'producer')) {
        $owned = Get-OwnedProcess $Record.$role
        if ($owned) {
            # The venv launcher can own a child interpreter; stop only this verified process tree.
            & taskkill /PID $owned.ProcessId /T /F | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "Could not stop owned $role process $($owned.ProcessId)." }
        }
    }
}

function Get-SourceStatus($Record) {
    $server = Get-OwnedProcess $Record.server
    $producer = Get-OwnedProcess $Record.producer
    $heartbeat = $null
    $sample = $null
    try { $heartbeat = Get-Content -LiteralPath (Join-Path $state 'server-health.json') -Raw | ConvertFrom-Json } catch { }
    try { $sample = Get-Content -LiteralPath (Join-Path $state 'values.json') -Raw | ConvertFrom-Json } catch { }
    $heartbeatAge = if ($heartbeat) { ([DateTimeOffset]::UtcNow - [DateTimeOffset]::Parse($heartbeat.heartbeatAtUtc)).TotalSeconds } else { $null }
    $sampleAge = if ($sample) { ([DateTimeOffset]::UtcNow - [DateTimeOffset]::Parse($sample.generatedAtUtc)).TotalSeconds } else { $null }
    return [pscustomobject]@{
        healthy = [bool]($server -and $producer -and $heartbeat -and $sample -and $heartbeat.sourceFresh -and
            $heartbeatAge -ge 0 -and $heartbeatAge -lt 45 -and $sampleAge -ge 0 -and $sampleAge -lt 120 -and
            [DateTimeOffset]::Parse($heartbeat.heartbeatAtUtc) -ge $server.CreationDate.ToUniversalTime() -and
            [DateTimeOffset]::Parse($sample.generatedAtUtc) -ge $producer.CreationDate.ToUniversalTime())
        producerPid = $producer.ProcessId
        serverPid = $server.ProcessId
        localIpAddress = $heartbeat.localIpAddress
        discoveryPort = $heartbeat.BroadcastPort
        heartbeatAgeSeconds = $heartbeatAge
        sampleAgeSeconds = $sampleAge
        devices = $heartbeat.devices
        stateDirectory = $state
    }
}

New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$record = if (Test-Path -LiteralPath $processFile) { Get-Content -LiteralPath $processFile -Raw | ConvertFrom-Json } else { $null }
if ($record -and ($record.ProducerPid -or $record.ServerPid)) {
    throw 'Legacy startup record found. Stop the previously verified manual processes before using this runner.'
}

switch ($Action) {
    'Setup' {
        if ((Get-OwnedProcess $record.server) -or (Get-OwnedProcess $record.producer)) { throw 'Stop this source before replacing its runtime.' }
        if (!(Test-Path -LiteralPath $producerPython)) {
            & $Python -m venv (Join-Path $runtime 'venv')
            if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
        }
        & $producerPython -m pip install --disable-pip-version-check -r (Join-Path $sourceRoot 'services/sources/requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Source dependency installation failed.' }
        & dotnet publish (Join-Path $PSScriptRoot 'server/Northlake.Bacnet.csproj') -c Release --artifacts-path $ArtifactsPath --no-self-contained -o (Join-Path $runtime 'server') --nologo -v minimal
        if ($LASTEXITCODE -ne 0) { throw 'BACnet server build failed.' }
        if (Test-Path -LiteralPath (Join-Path $EnergyHippoRoot 'src/Tasks/EEMSuite.Tasks.Gateways/Bacnet/BacnetClient.cs')) {
            & dotnet publish (Join-Path $PSScriptRoot 'verify/Northlake.Bacnet.Probe.csproj') -c Release --artifacts-path $ArtifactsPath "-p:EnergyHippoRoot=$EnergyHippoRoot" --no-self-contained -o (Join-Path $runtime 'probe') --nologo -v minimal
            if ($LASTEXITCODE -ne 0) { throw 'Collector client probe build failed.' }
        }
        Write-Output "Runtime prepared in $runtime. Start with the Workers host's current LAN IPv4 address."
    }
    'Start' {
        if ((Get-OwnedProcess $record.server) -or (Get-OwnedProcess $record.producer)) {
            $status = Get-SourceStatus $record
            if (!$status.healthy -or $status.localIpAddress -ne $LocalIpAddress) { throw 'An incomplete or differently bound source is already running. Inspect Status and use Stop before restarting.' }
            $status | ConvertTo-Json -Depth 5
            return
        }
        if (!(Test-Path -LiteralPath $producerPython) -or !(Test-Path -LiteralPath $serverExe)) { throw 'Run Setup first.' }
        $nic = @(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -eq $LocalIpAddress -and $_.AddressState -eq 'Preferred' })
        if ($nic.Count -ne 1) { throw 'LocalIpAddress must be an active local IPv4 address on the Workers host.' }
        $bindings = Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
        $occupied = @(Get-NetUDPEndpoint | Where-Object { $_.LocalPort -in $bindings.devices.unicastPort })
        if ($occupied.Count) { throw 'A configured BACnet unicast port is already occupied. Reconcile the owner before starting.' }
        $started = @{}
        try {
            $producer = Start-Process -FilePath $producerPython -ArgumentList @('-B', '-m', 'services.bacnet.producer', '--state', "`"$state`"", '--source-root', "`"$sourceRoot`"") -WorkingDirectory $sourceRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'producer.log') -RedirectStandardError (Join-Path $runtime 'producer.err.log') -PassThru
            Save-ProcessEntry $producer 'producer' $started
            $server = Start-Process -FilePath $serverExe -ArgumentList @("`"$config`"", "`"$state`"", $LocalIpAddress) -WorkingDirectory $sourceRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'server.log') -RedirectStandardError (Join-Path $runtime 'server.err.log') -PassThru
            Save-ProcessEntry $server 'server' $started
            $deadline = [DateTimeOffset]::UtcNow.AddSeconds(60)
            do {
                Start-Sleep -Milliseconds 250
                $status = Get-SourceStatus $started
                if ($status.healthy) { $status | ConvertTo-Json -Depth 5; return }
                if (!(Get-OwnedProcess $started.server) -or !(Get-OwnedProcess $started.producer)) { throw 'A source process exited. Inspect the .runtime error logs.' }
            } while ([DateTimeOffset]::UtcNow -lt $deadline)
            throw 'Source startup did not become healthy within 60 seconds.'
        } catch {
            Stop-OwnedProcesses $started
            throw
        }
    }
    'Stop' {
        Stop-OwnedProcesses $record
        if (Test-Path -LiteralPath $processFile) { Remove-Item -LiteralPath $processFile }
        Write-Output 'Stopped the owned Northlake BACnet processes. State is retained.'
    }
    'Status' {
        $status = Get-SourceStatus $record
        $status | ConvertTo-Json -Depth 5
        if (!$status.healthy) { exit 1 }
    }
    'Verify' {
        $status = Get-SourceStatus $record
        if (!$status.healthy) { throw 'Source is not healthy. Run Status and inspect its logs.' }
        if (!(Test-Path -LiteralPath $probeExe)) { throw 'Run Setup with an EnergyHippo checkout to build the read-only protocol probe.' }
        & $probeExe $config (Join-Path $state 'values.json') $status.localIpAddress
        if ($LASTEXITCODE -ne 0) { throw 'Real collector client verification failed.' }
    }
}
