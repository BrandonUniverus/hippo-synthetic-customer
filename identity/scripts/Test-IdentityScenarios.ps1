[CmdletBinding()]
param()

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

$connectionPaths = @(
    (Join-Path $script:IdentityScenarioConnectionDirectory "labA\connection.json"),
    (Join-Path $script:IdentityScenarioConnectionDirectory "labB\connection.json")
)
foreach ($connectionPath in $connectionPaths) {
    if (-not (Test-Path -LiteralPath $connectionPath -PathType Leaf)) {
        throw "Apply both realms from /configure/scenarios before running the scenario verifier."
    }
}
if (-not (Test-Path -LiteralPath $script:IdentityRootCertificate -PathType Leaf)) {
    $null = Copy-IdentityRootCertificate
}

& python -u (Join-Path $script:IdentityRoot "scripts\verify_scenarios.py") `
    --connection $connectionPaths[0] `
    --connection $connectionPaths[1] `
    --ca-file $script:IdentityRootCertificate
if ($LASTEXITCODE -ne 0) {
    throw "Two-realm identity scenario verification failed with exit code $LASTEXITCODE."
}
