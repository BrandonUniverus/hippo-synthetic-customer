[CmdletBinding(SupportsShouldProcess, ConfirmImpact = "High")]
param(
    [switch] $TrustCertificate,

    [ValidateSet("CurrentUser", "LocalMachine")]
    [string] $CertificateStoreLocation = "CurrentUser",

    [switch] $SkipVerification
)

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

Assert-IdentityPrerequisites
$volumeName = "$($script:IdentityComposeProject)_postgres-data"
$volumeExists = & docker volume inspect $volumeName --format "{{.Name}}" 2>$null

if (-not $PSCmdlet.ShouldProcess(
    $volumeName,
    "Delete the synthetic Keycloak database and recreate the deterministic Northlake realm"
)) {
    return
}

Invoke-IdentityCompose down --remove-orphans

if ($volumeExists) {
    $labels = & docker volume inspect $volumeName `
        --format "{{index .Labels `"com.docker.compose.project`"}}|{{index .Labels `"com.docker.compose.volume`"}}"
    if ($LASTEXITCODE -ne 0 -or $labels -ne "$($script:IdentityComposeProject)|postgres-data") {
        throw "Refusing to remove volume '$volumeName' because its Compose ownership labels did not match."
    }

    & docker volume rm $volumeName
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to remove the scoped synthetic identity database volume '$volumeName'."
    }
}

$rotationResult = Join-Path $script:IdentityRuntimeDirectory "last-key-rotation.json"
if (Test-Path -LiteralPath $rotationResult -PathType Leaf) {
    Remove-Item -LiteralPath $rotationResult
}

& (Join-Path $PSScriptRoot "Start-Identity.ps1") `
    -TrustCertificate:$TrustCertificate `
    -CertificateStoreLocation $CertificateStoreLocation `
    -SkipVerification:$SkipVerification
