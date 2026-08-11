[CmdletBinding()]
param(
    [switch] $ShowSecrets
)

. (Join-Path $PSScriptRoot "Identity.Common.ps1")

Assert-IdentityPrerequisites
Invoke-IdentityCompose ps

if (-not (Test-Path -LiteralPath $script:IdentityConnectionProfile -PathType Leaf)) {
    Write-Warning "Connection profile has not been generated. Run Start-Identity.ps1."
    return
}

$profile = Get-Content -LiteralPath $script:IdentityConnectionProfile -Raw | ConvertFrom-Json
Write-Host ""
Write-Host "Issuer:          $($profile.issuer)"
Write-Host "Realm source:    $($profile.realmSource.manifestId) v$($profile.realmSource.manifestVersion)"
Write-Host "Discovery:       $($profile.discoveryEndpoint)"
Write-Host "SAML metadata:   $($profile.samlMetadataEndpoint)"
Write-Host "Account console: $($profile.accountConsole)"
Write-Host "Admin console:   $($profile.adminConsole)"
Write-Host "Active user:     $($profile.testUsers.active.username)"
Write-Host "Disabled user:   $($profile.testUsers.disabled.username)"
if ($profile.PSObject.Properties["userInventory"]) {
    Write-Host "User inventory:  $($profile.userInventory.total) total, $($profile.userInventory.enabled) enabled, $($profile.userInventory.local) local"
}
if ($profile.PSObject.Properties["groupInventory"]) {
    Write-Host "Group inventory: $($profile.groupInventory.total) total, $($profile.groupInventory.local) local"
}
if ($profile.clients.PSObject.Properties["modern"]) {
    Write-Host "Modern client:   $($profile.clients.modern.clientId) (code + PKCE S256)"
    if ($profile.clients.PSObject.Properties["legacy"]) {
        Write-Host "Legacy client:   $($profile.clients.legacy.clientId) (historical id_token token)"
    }
    else {
        Write-Host "Legacy client:   disabled"
    }
    Write-Host "OIDC mode:       $($profile.clients.modern.configurationMode)"
    Write-Host "OIDC PAR:        $($profile.clients.modern.parBehavior)"
    Write-Host "OIDC auth:       $($profile.clients.modern.tokenEndpointAuthMethod)"
    Write-Host "OIDC scopes:     $($profile.clients.modern.scope)"
}
else {
    Write-Host "OIDC clients:    disabled"
}
if ($profile.clients.PSObject.Properties["saml"]) {
    Write-Host "SAML entity ID:  $($profile.clients.saml.entityId)"
    Write-Host "SAML ACS:        $($profile.clients.saml.defaultAssertionConsumerServiceUrl)"
    Write-Host "SAML logout:     $($profile.clients.saml.defaultSingleLogoutServiceUrl)"
}
else {
    Write-Host "SAML client:     disabled"
}
Write-Host "Profile:         $script:IdentityConnectionProfile"

if (Test-Path -LiteralPath $script:IdentityScenarioSettings -PathType Leaf) {
    $scenarioState = Get-Content -LiteralPath $script:IdentityScenarioSettings -Raw | ConvertFrom-Json
    Write-Host ""
    Write-Host "Scenario:        $($scenarioState.values.scenarioName)"
    Write-Host "Lab A issuer:     $($profile.baseUrl)/realms/$($scenarioState.values.realms.labA.realmKey)"
    Write-Host "Lab B issuer:     $($profile.baseUrl)/realms/$($scenarioState.values.realms.labB.realmKey)"
    Write-Host "Subject mode:     $(if ($scenarioState.values.sharedExternalSubject) { 'equal subject, distinct issuer' } else { 'distinct subject, distinct issuer' })"
}

if ($ShowSecrets) {
    Write-Host ""
    Write-Warning "Displaying local development secrets."
    Write-Host "Test password:        $($profile.testUsers.password)"
    Write-Host "Admin username:       $($profile.admin.username)"
    Write-Host "Admin password:       $($profile.admin.password)"
    if ($profile.clients.PSObject.Properties["modern"]) {
        Write-Host "Modern client secret: $($profile.clients.modern.clientSecret)"
        if ($profile.clients.PSObject.Properties["legacy"]) {
            Write-Host "Legacy client secret: $($profile.clients.legacy.clientSecret)"
        }
    }
}
