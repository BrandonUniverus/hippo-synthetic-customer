[CmdletBinding()]
param(
    [ValidateRange(60, 600)]
    [int] $TimeoutSeconds = 300
)

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

Assert-IdentityPrerequisites
if (-not (Test-Path -LiteralPath $script:IdentityConnectionProfile -PathType Leaf)) {
    throw "Connection profile is missing. Run Start-Identity.ps1 first."
}
if (-not (Test-Path -LiteralPath $script:IdentityRootCertificate -PathType Leaf)) {
    $null = Copy-IdentityRootCertificate
}
$null = New-Item -ItemType Directory -Path $script:IdentityEvidenceDirectory -Force
$beforePath = Join-Path $script:IdentityEvidenceDirectory "stable-before.json"
$afterPath = Join-Path $script:IdentityEvidenceDirectory "stable-after.json"

function New-StableSnapshot {
    param([Parameter(Mandatory = $true)][string] $OutputPath)

    & python $script:IdentityEvidenceScript snapshot `
        --connection $script:IdentityConnectionProfile `
        --ca-file $script:IdentityRootCertificate `
        --catalog $script:IdentityCoverageCatalog `
        --compose $script:IdentityComposeFile `
        --output $OutputPath
    if ($LASTEXITCODE -ne 0) {
        throw "Stable Northlake snapshot failed."
    }
}

function Wait-ForStableProvider {
    $environment = Get-IdentityEnvironment
    $issuer = "$($environment.IDENTITY_PUBLIC_BASE_URL.TrimEnd('/'))/realms/northlake"
    $discovery = "$issuer/.well-known/openid-configuration"
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-RestMethod -Uri $discovery -SkipCertificateCheck -TimeoutSec 5
            if ($response.issuer -eq $issuer) {
                return
            }
        }
        catch {
        }
        Start-Sleep -Seconds 2
    } while ([DateTimeOffset]::UtcNow -lt $deadline)
    throw "Stable Northlake provider did not recover within $TimeoutSeconds seconds."
}

New-StableSnapshot -OutputPath $beforePath
$environment = Get-IdentityEnvironment
$discoveryEndpoint = "$($environment.IDENTITY_PUBLIC_BASE_URL.TrimEnd('/'))/realms/northlake/.well-known/openid-configuration"
$outageObserved = $false
$keycloakStopped = $false
try {
    Invoke-IdentityCompose stop keycloak
    $keycloakStopped = $true
    try {
        $null = Invoke-WebRequest -Uri $discoveryEndpoint -SkipCertificateCheck -TimeoutSec 10
    }
    catch {
        $outageObserved = $true
    }
    if (-not $outageObserved) {
        throw "The explicit Keycloak outage was not observable through the public issuer."
    }
}
finally {
    if ($keycloakStopped) {
        Invoke-IdentityCompose start keycloak
        Wait-ForStableProvider
    }
}

Invoke-IdentityCompose restart
Wait-ForStableProvider
& (Join-Path $PSScriptRoot "Test-Identity.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "The provider did not pass its full protocol verifier after restart."
}
New-StableSnapshot -OutputPath $afterPath

$compareArguments = @(
    $script:IdentityEvidenceScript,
    "compare",
    "--before", $beforePath,
    "--after", $afterPath,
    "--output", $script:IdentityRestartEvidence
)
if ($outageObserved) {
    $compareArguments += "--outage-observed"
}
& python @compareArguments
if ($LASTEXITCODE -ne 0) {
    throw "Stable realm identity changed across outage recovery or restart."
}
Write-Host "[OK] Outage and recovery were observed, then the full stack restarted."
Write-Host "[OK] Issuer, subjects, keys, SAML metadata, clients, image, and configuration stayed stable."
