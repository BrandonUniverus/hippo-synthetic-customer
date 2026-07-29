[CmdletBinding()]
param(
    [switch] $SkipVerification
)

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

Assert-IdentityPrerequisites
if (-not (Test-Path -LiteralPath $script:IdentityConnectionProfile -PathType Leaf)) {
    throw "Connection profile is missing. Run Start-Identity.ps1 first."
}
if (-not (Test-Path -LiteralPath $script:IdentityRootCertificate -PathType Leaf)) {
    $null = Copy-IdentityRootCertificate
}

& python (Join-Path $script:IdentityRoot "scripts\rotate_signing_key.py") `
    --connection $script:IdentityConnectionProfile `
    --ca-file $script:IdentityRootCertificate `
    --result (Join-Path $script:IdentityRuntimeDirectory "last-key-rotation.json")
if ($LASTEXITCODE -ne 0) {
    throw "Synthetic identity signing-key rotation failed with exit code $LASTEXITCODE."
}

if (-not $SkipVerification) {
    & (Join-Path $PSScriptRoot "Test-Identity.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "Post-rotation identity verification failed."
    }
}
