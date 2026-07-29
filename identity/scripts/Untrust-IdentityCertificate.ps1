[CmdletBinding(SupportsShouldProcess, ConfirmImpact = "High")]
param(
    [ValidateSet("CurrentUser", "LocalMachine")]
    [string] $StoreLocation = "CurrentUser"
)

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

$thumbprintPath = Join-Path $script:IdentityCertificateDirectory "trusted-$($StoreLocation.ToLowerInvariant())-thumbprint.txt"
if (-not (Test-Path -LiteralPath $thumbprintPath -PathType Leaf)) {
    Write-Host "[OK] No recorded $StoreLocation trust entry exists."
    return
}

$thumbprint = (Get-Content -LiteralPath $thumbprintPath -Raw).Trim()
if ($thumbprint -notmatch "^[0-9A-Fa-f]{40,64}$") {
    throw "Recorded certificate thumbprint is invalid: '$thumbprint'."
}

$certificatePath = "Cert:\$StoreLocation\Root\$thumbprint"
if (-not (Test-Path -LiteralPath $certificatePath)) {
    Write-Host "[OK] Certificate is no longer present in $StoreLocation root trust."
    return
}

if ($PSCmdlet.ShouldProcess($certificatePath, "Remove the synthetic identity development CA")) {
    Remove-Item -LiteralPath $certificatePath
    Write-Host "[OK] Removed synthetic identity CA $thumbprint from $StoreLocation root trust."
}
