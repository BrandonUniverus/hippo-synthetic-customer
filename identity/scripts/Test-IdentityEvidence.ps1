[CmdletBinding()]
param(
    [string] $EemRepositoryRoot = "C:\Hippo\Git\univerus\energyhippo"
)

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

Assert-IdentityPrerequisites
if (-not (Test-Path -LiteralPath $EemRepositoryRoot -PathType Container)) {
    throw "EnergyHippo repository was not found at $EemRepositoryRoot."
}
$null = New-Item -ItemType Directory -Path $script:IdentityEvidenceDirectory -Force
$commandResults = [System.Collections.Generic.List[object]]::new()

function Invoke-EvidenceProcess {
    param(
        [Parameter(Mandatory = $true)][string] $Id,
        [Parameter(Mandatory = $true)][string] $FilePath,
        [Parameter(Mandatory = $true)][string[]] $ArgumentList
    )

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $null = & $FilePath @ArgumentList 2>&1
    $exitCode = $LASTEXITCODE
    $stopwatch.Stop()
    $passed = $exitCode -eq 0
    $commandResults.Add([ordered]@{
        id = $Id
        passed = $passed
        exitCode = $exitCode
        durationMilliseconds = $stopwatch.ElapsedMilliseconds
    })
    Write-Host "[$(if ($passed) { 'OK' } else { 'FAIL' })] $Id"
}

Invoke-EvidenceProcess `
    -Id "catalog-validation" `
    -FilePath "python" `
    -ArgumentList @(
        $script:IdentityEvidenceScript,
        "validate",
        "--repository-root", $script:RepositoryRoot,
        "--catalog", $script:IdentityCoverageCatalog,
        "--faults", $script:IdentityFaultCatalog
    )
Invoke-EvidenceProcess `
    -Id "unit-tests" `
    -FilePath "python" `
    -ArgumentList @("-m", "unittest", "discover", "-s", (Join-Path $script:IdentityRoot "tests"))
Invoke-EvidenceProcess `
    -Id "stable-promotion" `
    -FilePath "pwsh" `
    -ArgumentList @("-NoProfile", "-File", (Join-Path $PSScriptRoot "Promote-IdentityStableRealm.ps1"))
Invoke-EvidenceProcess `
    -Id "full-provider" `
    -FilePath "pwsh" `
    -ArgumentList @("-NoProfile", "-File", (Join-Path $PSScriptRoot "Test-Identity.ps1"))
Invoke-EvidenceProcess `
    -Id "oidc-baseline" `
    -FilePath "pwsh" `
    -ArgumentList @("-NoProfile", "-File", (Join-Path $PSScriptRoot "Test-OidcIdentity.ps1"))
Invoke-EvidenceProcess `
    -Id "saml-baseline" `
    -FilePath "pwsh" `
    -ArgumentList @("-NoProfile", "-File", (Join-Path $PSScriptRoot "Test-SamlIdentity.ps1"))
Invoke-EvidenceProcess `
    -Id "group-claims" `
    -FilePath "pwsh" `
    -ArgumentList @(
        "-NoProfile",
        "-File", (Join-Path $PSScriptRoot "Test-IdentityGroupClaims.ps1"),
        "-Username", "samantha.ireland"
    )
Invoke-EvidenceProcess `
    -Id "scenarios" `
    -FilePath "pwsh" `
    -ArgumentList @("-NoProfile", "-File", (Join-Path $PSScriptRoot "Test-IdentityScenarios.ps1"))
Invoke-EvidenceProcess `
    -Id "browser-lab" `
    -FilePath "pwsh" `
    -ArgumentList @("-NoProfile", "-File", (Join-Path $PSScriptRoot "Test-IdentityBrowserLab.ps1"))
Invoke-EvidenceProcess `
    -Id "restart-stability" `
    -FilePath "pwsh" `
    -ArgumentList @("-NoProfile", "-File", (Join-Path $PSScriptRoot "Test-IdentityRestartStability.ps1"))

$commandDocument = [ordered]@{
    schemaVersion = 1
    recordedAtUtc = [DateTimeOffset]::UtcNow.ToString("o")
    commands = $commandResults
}
[System.IO.File]::WriteAllText(
    $script:IdentityCommandEvidence,
    ($commandDocument | ConvertTo-Json -Depth 10) + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
)

& python $script:IdentityEvidenceScript export `
    --repository-root $script:RepositoryRoot `
    --eem-repository-root $EemRepositoryRoot `
    --catalog $script:IdentityCoverageCatalog `
    --faults $script:IdentityFaultCatalog `
    --runtime $script:IdentityRuntimeDirectory `
    --commands $script:IdentityCommandEvidence `
    --restart $script:IdentityRestartEvidence `
    --output $script:IdentityEvidenceManifest
if ($LASTEXITCODE -ne 0) {
    throw "Northlake evidence export found a required local failure."
}

$failedCommands = @($commandResults | Where-Object { -not $_.passed })
if ($failedCommands.Count -gt 0) {
    throw "Northlake evidence commands failed: $($failedCommands.id -join ', ')."
}
Write-Host "[OK] Redacted Phase 9 evidence exported to $script:IdentityEvidenceManifest."
