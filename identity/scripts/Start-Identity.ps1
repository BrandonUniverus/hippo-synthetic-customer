[CmdletBinding()]
param(
    [switch] $TrustCertificate,

    [ValidateSet("CurrentUser", "LocalMachine")]
    [string] $CertificateStoreLocation = "CurrentUser",

    [switch] $SkipVerification,

    [ValidateRange(30, 600)]
    [int] $TimeoutSeconds = 240
)

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

if (-not (Test-Path -LiteralPath $script:IdentityEnvironmentFile -PathType Leaf)) {
    & (Join-Path $PSScriptRoot "Initialize-Identity.ps1") -Confirm:$false
    if (-not (Test-Path -LiteralPath $script:IdentityEnvironmentFile -PathType Leaf)) {
        throw "Identity initialization did not create $script:IdentityEnvironmentFile."
    }
}

Assert-IdentityPrerequisites
New-IdentityRealm

& docker compose `
    --project-directory $script:IdentityRoot `
    --env-file $script:IdentityEnvironmentFile `
    --file $script:IdentityComposeFile `
    config --quiet
if ($LASTEXITCODE -ne 0) {
    throw "Identity compose configuration is invalid."
}

Invoke-IdentityCompose up --detach --remove-orphans

$environment = Get-IdentityEnvironment
$discoveryEndpoint = "$($environment.IDENTITY_PUBLIC_BASE_URL.TrimEnd('/'))/realms/northlake/.well-known/openid-configuration"
$deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
$lastFailure = $null

do {
    try {
        $response = Invoke-RestMethod -Uri $discoveryEndpoint -SkipCertificateCheck -TimeoutSec 5
        if ($response.issuer -eq "$($environment.IDENTITY_PUBLIC_BASE_URL.TrimEnd('/'))/realms/northlake") {
            $lastFailure = $null
            break
        }
        $lastFailure = "Discovery returned an unexpected issuer '$($response.issuer)'."
    }
    catch {
        $lastFailure = $_.Exception.Message
    }
    Start-Sleep -Seconds 2
} while ([DateTimeOffset]::UtcNow -lt $deadline)

if ($lastFailure) {
    Invoke-IdentityCompose ps
    Invoke-IdentityCompose logs --tail 100 keycloak caddy
    throw "Identity provider did not become ready within $TimeoutSeconds seconds. Last error: $lastFailure"
}

$null = Copy-IdentityRootCertificate

if ($TrustCertificate) {
    & (Join-Path $PSScriptRoot "Trust-IdentityCertificate.ps1") `
        -StoreLocation $CertificateStoreLocation `
        -Confirm:$false
}

if (-not $SkipVerification) {
    & (Join-Path $PSScriptRoot "Test-Identity.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "Identity verification failed."
    }
}

Write-Host ""
Write-Host "[OK] Northlake Synthetic Identity is ready."
Write-Host "Issuer:        $($environment.IDENTITY_PUBLIC_BASE_URL.TrimEnd('/'))/realms/northlake"
Write-Host "Login/account: $($environment.IDENTITY_PUBLIC_BASE_URL.TrimEnd('/'))/realms/northlake/account/"
Write-Host "Admin:         $($environment.IDENTITY_PUBLIC_BASE_URL.TrimEnd('/'))/admin/northlake/console/"
Write-Host "SAML metadata: $($environment.IDENTITY_PUBLIC_BASE_URL.TrimEnd('/'))/realms/northlake/protocol/saml/descriptor"
Write-Host "Credentials:   $script:IdentityConnectionProfile"

$certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new(
    $script:IdentityRootCertificate
)
$trustedCertificatePath = "Cert:\$CertificateStoreLocation\Root\$($certificate.Thumbprint)"
if (-not (Test-Path -LiteralPath $trustedCertificatePath)) {
    Write-Host ""
    Write-Warning "The local CA has not been trusted. Before pointing EEMSuite or a browser at this issuer, run:"
    Write-Host "  pwsh .\identity\scripts\Trust-IdentityCertificate.ps1"
}
