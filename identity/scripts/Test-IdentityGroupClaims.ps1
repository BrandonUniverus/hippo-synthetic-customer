[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9][a-z0-9._-]{2,63}$')]
    [string] $Username
)

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

Assert-IdentityPrerequisites
foreach ($requiredPath in @($script:IdentityConnectionProfile, $script:IdentityRealmOutput)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Generated identity state is missing. Run Start-Identity.ps1 first."
    }
}
if (-not (Test-Path -LiteralPath $script:IdentityRootCertificate -PathType Leaf)) {
    $null = Copy-IdentityRootCertificate
}

& python -u (Join-Path $script:IdentityRoot "scripts\verify_group_claims.py") `
    --connection $script:IdentityConnectionProfile `
    --realm $script:IdentityRealmOutput `
    --ca-file $script:IdentityRootCertificate `
    --username $Username
if ($LASTEXITCODE -ne 0) {
    throw "Synthetic identity group-claim verification failed with exit code $LASTEXITCODE."
}
