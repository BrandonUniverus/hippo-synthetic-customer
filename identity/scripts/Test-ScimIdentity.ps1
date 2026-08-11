[CmdletBinding()]
param(
    [ValidateSet("Discovery", "Lifecycle", "Deactivate", "Reactivate")]
    [string] $Mode = "Discovery",
    [string] $ConnectionKey = "eem-local",
    [string] $SyntheticUserId = "samantha.ireland",
    [string] $GroupBindingKey = "nlu-company-admins"
)

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

Assert-IdentityPrerequisites
$environment = Get-IdentityEnvironment
$publicBaseUrl = [string] $environment["IDENTITY_PUBLIC_BASE_URL"]
if ([string]::IsNullOrWhiteSpace($publicBaseUrl)) {
    throw "IDENTITY_PUBLIC_BASE_URL is missing."
}

$action = if ($Mode -eq "Discovery") { "verify" } else { $Mode.ToLowerInvariant() }
$values = @{ connectionKey = $ConnectionKey }
if ($Mode -eq "Lifecycle") {
    $values["syntheticUserId"] = $SyntheticUserId
    $values["groupBindingKey"] = $GroupBindingKey
}
$body = @{ values = $values } | ConvertTo-Json -Depth 8 -Compress
$uri = "$($publicBaseUrl.TrimEnd('/'))/configure/api/scim/$action"

try {
    $response = Invoke-RestMethod `
        -Uri $uri `
        -Method Post `
        -ContentType "application/json" `
        -Body $body `
        -TimeoutSec 180
}
catch {
    throw "Northlake SCIM $Mode request failed before a redacted result was returned: $($_.Exception.Message)"
}

$result = if ($response.PSObject.Properties["verification"]) {
    $response.verification
}
elseif ($response.PSObject.Properties["lifecycle"]) {
    $response.lifecycle
}
else {
    throw "Northlake SCIM $Mode returned no verification or lifecycle result."
}

$result | ConvertTo-Json -Depth 20
if (-not $result.passed) {
    throw "Northlake SCIM $Mode found a $($result.classification) break."
}
