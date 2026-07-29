[CmdletBinding()]
param()

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

Assert-IdentityPrerequisites
Invoke-IdentityCompose stop
Write-Host "[OK] Synthetic identity containers stopped. Database, realm, keys, and CA were preserved."
