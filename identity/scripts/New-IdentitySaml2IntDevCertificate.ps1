[CmdletBinding()]
param(
    [ValidateRange(1, 7300)]
    [int] $Days = 365,

    [switch] $Force
)

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

$arguments = @(
    (Join-Path $script:IdentityRoot "scripts\create_saml2int_dev_certificate.py"),
    "--certificate-file", $script:IdentitySaml2IntCertificate,
    "--days", $Days
)
if ($Force) {
    $arguments += "--force"
}

& python -u @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Saml2Int development certificate generation failed with exit code $LASTEXITCODE."
}
