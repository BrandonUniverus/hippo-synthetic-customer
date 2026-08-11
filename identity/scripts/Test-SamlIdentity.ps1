[CmdletBinding()]
param()

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

Assert-IdentityPrerequisites
if (-not (Test-Path -LiteralPath $script:IdentityConnectionProfile -PathType Leaf)) {
    throw "Connection profile is missing. Run Start-Identity.ps1 first."
}
if (-not (Test-Path -LiteralPath $script:IdentityRootCertificate -PathType Leaf)) {
    $null = Copy-IdentityRootCertificate
}

& python -u (Join-Path $script:IdentityRoot "scripts\verify_saml_baseline.py") `
    --connection $script:IdentityConnectionProfile `
    --ca-file $script:IdentityRootCertificate
if ($LASTEXITCODE -ne 0) {
    throw "Synthetic SAML protocol verification failed with exit code $LASTEXITCODE."
}
