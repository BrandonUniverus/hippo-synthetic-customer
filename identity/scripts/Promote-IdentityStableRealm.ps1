[CmdletBinding()]
param()

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

Assert-IdentityPrerequisites
$environment = Get-IdentityEnvironment
if ($environment.NORTHLAKE_REALM_KEY -ne "northlake") {
    throw "Stable promotion is restricted to the exact northlake realm."
}

$publicBaseUrl = [string] $environment.IDENTITY_PUBLIC_BASE_URL
$configurationBaseUrl = "$($publicBaseUrl.TrimEnd('/'))/configure/api"
function Invoke-ConfigurationGet {
    param([Parameter(Mandatory = $true)][string] $Path)

    return Invoke-RestMethod `
        -Uri "$configurationBaseUrl/$Path" `
        -Method Get `
        -SkipCertificateCheck `
        -TimeoutSec 30
}

function Invoke-ConfigurationPost {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][object] $Values
    )

    $body = @{ values = $Values } | ConvertTo-Json -Depth 30 -Compress
    return Invoke-RestMethod `
        -Uri "$configurationBaseUrl/$Path" `
        -Method Post `
        -ContentType "application/json" `
        -Body $body `
        -SkipCertificateCheck `
        -TimeoutSec 180
}

$providerState = Invoke-ConfigurationGet -Path "state"
if ($providerState.values.realmKey -ne "northlake") {
    throw "The running configuration service is not bound to the stable northlake realm."
}
$oidcState = Invoke-ConfigurationGet -Path "oidc"
$samlState = Invoke-ConfigurationGet -Path "saml"
$oidcValues = $oidcState.values
$samlValues = $samlState.values

$changed = $false
$desiredOidc = @{
    configurationMode = "Discovery"
    parBehavior = "UseIfAvailable"
    tokenEndpointAuthMethod = "ClientSecretPost"
    modernConsentRequired = $false
    legacyEnabled = $false
}
foreach ($key in $desiredOidc.Keys) {
    if ($oidcValues.$key -ne $desiredOidc[$key]) {
        $oidcValues.$key = $desiredOidc[$key]
        $changed = $true
    }
}

$desiredSaml = @{
    standardEnabled = $true
    standardSubjectBindingKind = "PersistentNameId"
    standardSubjectAttribute = ""
    standardAllowUnsolicitedResponses = $false
    standardEnableSingleLogout = $true
    saml2IntEnabled = $false
}
foreach ($key in $desiredSaml.Keys) {
    if ($samlValues.$key -ne $desiredSaml[$key]) {
        $samlValues.$key = $desiredSaml[$key]
        $changed = $true
    }
}

if ($changed) {
    $null = Invoke-ConfigurationPost -Path "saml/save" -Values $samlValues
    $null = Invoke-ConfigurationPost -Path "oidc/save" -Values $oidcValues
    $applied = Invoke-ConfigurationPost -Path "oidc/apply" -Values $oidcValues
    if (-not $applied.applied -or -not $applied.verification.passed) {
        throw "The stable Northlake realm did not pass its focused OIDC verification after promotion."
    }
}

& (Join-Path $PSScriptRoot "Test-OidcIdentity.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "Stable promotion OIDC verification failed."
}
& (Join-Path $PSScriptRoot "Test-SamlIdentity.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "Stable promotion SAML verification failed."
}
$oidcVerification = Invoke-ConfigurationPost -Path "oidc/verify" -Values @{}
if (-not $oidcVerification.verification.passed) {
    throw "Stable promotion could not persist passing OIDC evidence."
}
$samlVerification = Invoke-ConfigurationPost -Path "saml/verify" -Values @{}
if (-not $samlVerification.verification.passed) {
    throw "Stable promotion could not persist passing SAML evidence."
}

$null = New-Item -ItemType Directory -Path $script:IdentityEvidenceDirectory -Force
$snapshotPath = Join-Path $script:IdentityEvidenceDirectory "stable-promotion-snapshot.json"
& python $script:IdentityEvidenceScript snapshot `
    --connection $script:IdentityConnectionProfile `
    --ca-file $script:IdentityRootCertificate `
    --catalog $script:IdentityCoverageCatalog `
    --compose $script:IdentityComposeFile `
    --output $snapshotPath
if ($LASTEXITCODE -ne 0) {
    throw "Stable promotion snapshot verification failed."
}
$snapshot = Get-Content -LiteralPath $snapshotPath -Raw | ConvertFrom-Json
$result = [ordered]@{
    schemaVersion = 1
    checkedAtUtc = [DateTimeOffset]::UtcNow.ToString("o")
    passed = $true
    classification = "stable-realm-promoted"
    changed = $changed
    realm = $snapshot.realm
    issuer = $snapshot.issuer
    stableClients = $snapshot.stableClients
    configurationHash = $snapshot.configurationHash
    faultControlsPermitted = $false
    redacted = $true
}
$resultPath = Join-Path $script:IdentityEvidenceDirectory "stable-promotion.json"
[System.IO.File]::WriteAllText(
    $resultPath,
    ($result | ConvertTo-Json -Depth 10) + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
)
Write-Host "[OK] Stable Northlake realm contains one normal OIDC and one normal SAML registration."
Write-Host "[OK] Destructive lab realms and fault recipes remain separate."
