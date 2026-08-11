[CmdletBinding()]
param()

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

$connectionPaths = @(
    (Join-Path $script:IdentityScenarioConnectionDirectory "labA\connection.json"),
    (Join-Path $script:IdentityScenarioConnectionDirectory "labB\connection.json")
)
foreach ($connectionPath in $connectionPaths) {
    if (-not (Test-Path -LiteralPath $connectionPath -PathType Leaf)) {
        throw "Apply both realms from /configure/scenarios before running the browser-lab verifier."
    }
}
if (-not (Test-Path -LiteralPath $script:IdentityRootCertificate -PathType Leaf)) {
    $null = Copy-IdentityRootCertificate
}

& python -u (Join-Path $script:IdentityRoot "scripts\verify_browser_lab.py") `
    --connection $connectionPaths[0] `
    --connection $connectionPaths[1] `
    --ca-file $script:IdentityRootCertificate
if ($LASTEXITCODE -ne 0) {
    throw "Northlake browser-lab verification failed with exit code $LASTEXITCODE."
}
