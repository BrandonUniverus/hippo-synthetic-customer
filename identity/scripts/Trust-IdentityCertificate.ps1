[CmdletBinding(SupportsShouldProcess, ConfirmImpact = "High")]
param(
    [ValidateSet("CurrentUser", "LocalMachine")]
    [string] $StoreLocation = "CurrentUser"
)

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

if (-not (Test-Path -LiteralPath $script:IdentityRootCertificate -PathType Leaf)) {
    $null = Copy-IdentityRootCertificate
}

$certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new(
    $script:IdentityRootCertificate
)
$storePath = "Cert:\$StoreLocation\Root"
$existingPath = Join-Path $storePath $certificate.Thumbprint
$thumbprintPath = Join-Path $script:IdentityCertificateDirectory "trusted-$($StoreLocation.ToLowerInvariant())-thumbprint.txt"

if (Test-Path -LiteralPath $existingPath) {
    $certificate.Thumbprint | Set-Content -LiteralPath $thumbprintPath -Encoding ascii
    Write-Host "[OK] Caddy local root is already trusted in $storePath."
    return
}

if (-not $PSCmdlet.ShouldProcess(
    $storePath,
    "Trust Caddy local development root certificate $($certificate.Thumbprint)"
)) {
    return
}

if ($StoreLocation -eq "LocalMachine") {
    $isAdministrator = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
    if (-not $isAdministrator) {
        throw "LocalMachine trust requires an elevated PowerShell session."
    }
}

$imported = Import-Certificate `
    -FilePath $script:IdentityRootCertificate `
    -CertStoreLocation $storePath
if (-not $imported) {
    throw "Certificate import did not return a certificate."
}

$certificate.Thumbprint | Set-Content -LiteralPath $thumbprintPath -Encoding ascii
Write-Host "[OK] Trusted Caddy local root $($certificate.Thumbprint) in $storePath."
