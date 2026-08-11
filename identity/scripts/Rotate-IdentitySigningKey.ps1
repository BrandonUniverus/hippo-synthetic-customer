[CmdletBinding()]
param(
    [switch] $SkipVerification,
    [switch] $VerifyExistingResult
)

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

Assert-IdentityPrerequisites
if (-not (Test-Path -LiteralPath $script:IdentityConnectionProfile -PathType Leaf)) {
    throw "Connection profile is missing. Run Start-Identity.ps1 first."
}
if (-not (Test-Path -LiteralPath $script:IdentityRootCertificate -PathType Leaf)) {
    $null = Copy-IdentityRootCertificate
}
$rotationResultPath = Join-Path $script:IdentityRuntimeDirectory "last-key-rotation.json"
$null = New-Item -ItemType Directory -Path $script:IdentityEvidenceDirectory -Force
$beforeSnapshotPath = Join-Path $script:IdentityEvidenceDirectory "stable-pre-rotation.json"
$afterSnapshotPath = Join-Path $script:IdentityEvidenceDirectory "stable-post-rotation.json"

if (-not $VerifyExistingResult) {
    & python $script:IdentityEvidenceScript snapshot `
        --connection $script:IdentityConnectionProfile `
        --ca-file $script:IdentityRootCertificate `
        --catalog $script:IdentityCoverageCatalog `
        --compose $script:IdentityComposeFile `
        --output $beforeSnapshotPath
    if ($LASTEXITCODE -ne 0) {
        throw "Pre-rotation stable identity snapshot failed."
    }

    & python (Join-Path $script:IdentityRoot "scripts\rotate_signing_key.py") `
        --connection $script:IdentityConnectionProfile `
        --ca-file $script:IdentityRootCertificate `
        --result $rotationResultPath
    if ($LASTEXITCODE -ne 0) {
        throw "Synthetic identity signing-key rotation failed with exit code $LASTEXITCODE."
    }
}
elseif (-not (Test-Path -LiteralPath $rotationResultPath -PathType Leaf)) {
    throw "No existing signing-key rotation result is available to verify."
}

if (-not $SkipVerification) {
    & (Join-Path $PSScriptRoot "Test-Identity.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "Post-rotation identity verification failed."
    }

    & python $script:IdentityEvidenceScript snapshot `
        --connection $script:IdentityConnectionProfile `
        --ca-file $script:IdentityRootCertificate `
        --catalog $script:IdentityCoverageCatalog `
        --compose $script:IdentityComposeFile `
        --output $afterSnapshotPath
    if ($LASTEXITCODE -ne 0) {
        throw "Post-rotation stable identity snapshot failed."
    }
    if (-not (Test-Path -LiteralPath $beforeSnapshotPath -PathType Leaf)) {
        $beforeSnapshotPath = Join-Path $script:IdentityEvidenceDirectory "stable-promotion-snapshot.json"
    }
    $beforeSnapshot = Get-Content -LiteralPath $beforeSnapshotPath -Raw | ConvertFrom-Json
    $afterSnapshot = Get-Content -LiteralPath $afterSnapshotPath -Raw | ConvertFrom-Json
    $beforeCertificates = @($beforeSnapshot.samlMetadata.certificateSha256)
    $afterCertificates = @($afterSnapshot.samlMetadata.certificateSha256)
    $oldCertificatesRetained = @($beforeCertificates | Where-Object { $_ -notin $afterCertificates }).Count -eq 0
    if (-not $oldCertificatesRetained -or $afterCertificates.Count -le $beforeCertificates.Count) {
        throw "SAML metadata did not retain the previous certificate alongside the new signing certificate."
    }

    $rotation = Get-Content -LiteralPath $rotationResultPath -Raw | ConvertFrom-Json
    $rotation | Add-Member -NotePropertyName postVerificationPassed -NotePropertyValue $true -Force
    $rotation | Add-Member -NotePropertyName samlMetadataOldCertificatesRetained -NotePropertyValue $true -Force
    $rotation | Add-Member -NotePropertyName samlMetadataCertificateCount -NotePropertyValue $afterCertificates.Count -Force
    [System.IO.File]::WriteAllText(
        $rotationResultPath,
        ($rotation | ConvertTo-Json -Depth 20) + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false)
    )
}
