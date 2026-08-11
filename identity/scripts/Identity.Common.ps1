Set-StrictMode -Version Latest

$script:IdentityRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$script:RepositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $script:IdentityRoot ".."))
$script:IdentityComposeFile = Join-Path $script:IdentityRoot "compose.yml"
$script:IdentityEnvironmentFile = Join-Path $script:IdentityRoot ".env"
$script:IdentityRuntimeDirectory = Join-Path $script:IdentityRoot ".runtime"
$script:IdentityImportDirectory = Join-Path $script:IdentityRuntimeDirectory "import"
$script:IdentityConnectionProfile = Join-Path $script:IdentityRuntimeDirectory "connection.json"
$script:IdentityConfigurationSettings = Join-Path $script:IdentityRuntimeDirectory "configuration.json"
$script:IdentityConfigurationModel = Join-Path $script:IdentityRoot "configuration\settings.py"
$script:IdentityOidcSettings = Join-Path $script:IdentityRuntimeDirectory "oidc.json"
$script:IdentityOidcConfigurationModel = Join-Path $script:IdentityRoot "configuration\oidc.py"
$script:IdentitySamlSettings = Join-Path $script:IdentityRuntimeDirectory "saml.json"
$script:IdentitySamlConfigurationModel = Join-Path $script:IdentityRoot "configuration\saml.py"
$script:IdentityScenarioSettings = Join-Path $script:IdentityRuntimeDirectory "scenarios.json"
$script:IdentityScenarioModel = Join-Path $script:IdentityRoot "configuration\scenarios.py"
$script:IdentityScenarioConnectionDirectory = Join-Path $script:IdentityRuntimeDirectory "scenarios"
$script:IdentityUserOverlay = Join-Path $script:IdentityRuntimeDirectory "users.json"
$script:IdentityGroupOverlay = Join-Path $script:IdentityRuntimeDirectory "groups.json"
$script:IdentityCertificateDirectory = Join-Path $script:IdentityRuntimeDirectory "certs"
$script:IdentityRootCertificate = Join-Path $script:IdentityCertificateDirectory "caddy-local-root.crt"
$script:IdentitySaml2IntCertificate = Join-Path $script:IdentityCertificateDirectory "saml2int-sp-public.cer"
$script:IdentityManifest = Join-Path $script:RepositoryRoot "security\northlake-eem-security-v1.yaml"
$script:IdentityRealmGenerator = Join-Path $script:IdentityRoot "realm\generate_realm.py"
$script:IdentityRealmOutput = Join-Path $script:IdentityImportDirectory "northlake-realm.json"
$script:IdentityComposeProject = "hippo-synthetic-identity"

function Assert-IdentityPrerequisites {
    foreach ($commandName in @("docker", "python")) {
        if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
            throw "Required command '$commandName' was not found on PATH."
        }
    }

    & docker info --format "{{.ServerVersion}}" *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker is installed, but the Docker engine is not available."
    }

    & python -c "import cryptography, lxml, signxml, yaml" *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Python identity dependencies are missing. Run: python -m pip install -r `"$script:IdentityRoot\requirements.txt`""
    }
}

function Get-IdentityEnvironment {
    if (-not (Test-Path -LiteralPath $script:IdentityEnvironmentFile -PathType Leaf)) {
        throw "Identity environment file is missing. Run Initialize-Identity.ps1 first."
    }

    $values = @{}
    foreach ($rawLine in Get-Content -LiteralPath $script:IdentityEnvironmentFile) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#", [System.StringComparison]::Ordinal)) {
            continue
        }

        $separator = $line.IndexOf("=")
        if ($separator -le 0) {
            throw "Invalid .env entry: '$rawLine'. Expected KEY=VALUE."
        }

        $values[$line.Substring(0, $separator).Trim()] = $line.Substring($separator + 1).Trim()
    }

    $defaults = @{
        NORTHLAKE_PROVIDER_DISPLAY_NAME = "Northlake Synthetic Identity"
        NORTHLAKE_REALM_KEY = "northlake"
        NORTHLAKE_ENABLE_OIDC = "true"
        NORTHLAKE_ENABLE_SAML = "true"
    }
    foreach ($key in $defaults.Keys) {
        if (-not $values.ContainsKey($key)) {
            $values[$key] = $defaults[$key]
        }
    }

    if (Test-Path -LiteralPath $script:IdentityConfigurationSettings -PathType Leaf) {
        $overlayJson = & python $script:IdentityConfigurationModel `
            --settings-file $script:IdentityConfigurationSettings `
            --print-environment-overlay
        if ($LASTEXITCODE -ne 0) {
            throw "Saved provider configuration is invalid. Open /configure or remove the ignored settings document."
        }
        $overlay = $overlayJson | ConvertFrom-Json -AsHashtable
        foreach ($key in $overlay.Keys) {
            $values[$key] = [string] $overlay[$key]
        }
    }
    if (Test-Path -LiteralPath $script:IdentityOidcSettings -PathType Leaf) {
        $oidcOverlayJson = & python $script:IdentityOidcConfigurationModel `
            --settings-file $script:IdentityOidcSettings `
            --print-environment-overlay
        if ($LASTEXITCODE -ne 0) {
            throw "Saved OIDC configuration is invalid. Open /configure/oidc or remove the ignored settings document."
        }
        $oidcOverlay = $oidcOverlayJson | ConvertFrom-Json -AsHashtable
        foreach ($key in $oidcOverlay.Keys) {
            $values[$key] = [string] $oidcOverlay[$key]
        }
    }
    if (Test-Path -LiteralPath $script:IdentitySamlSettings -PathType Leaf) {
        $samlOverlayJson = & python $script:IdentitySamlConfigurationModel `
            --settings-file $script:IdentitySamlSettings `
            --certificate-file $script:IdentitySaml2IntCertificate `
            --print-environment-overlay
        if ($LASTEXITCODE -ne 0) {
            throw "Saved SAML configuration is invalid. Open /configure/saml or remove the ignored settings document."
        }
        $samlOverlay = $samlOverlayJson | ConvertFrom-Json -AsHashtable
        foreach ($key in $samlOverlay.Keys) {
            $values[$key] = [string] $samlOverlay[$key]
        }
    }
    return $values
}

function Invoke-IdentityCompose {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]] $ArgumentList
    )

    $environment = Get-IdentityEnvironment
    $previousValues = @{}
    try {
        foreach ($key in $environment.Keys) {
            $previousValues[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
            [Environment]::SetEnvironmentVariable($key, $environment[$key], "Process")
        }

        & docker compose `
            --project-directory $script:IdentityRoot `
            --env-file $script:IdentityEnvironmentFile `
            --file $script:IdentityComposeFile `
            @ArgumentList
        if ($LASTEXITCODE -ne 0) {
            throw "docker compose failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        foreach ($key in $previousValues.Keys) {
            [Environment]::SetEnvironmentVariable($key, $previousValues[$key], "Process")
        }
    }
}

function New-IdentityRuntimeDirectories {
    foreach ($path in @(
        $script:IdentityRuntimeDirectory,
        $script:IdentityImportDirectory,
        $script:IdentityCertificateDirectory
    )) {
        $null = New-Item -ItemType Directory -Path $path -Force
    }
}

function New-IdentityRealm {
    New-IdentityRuntimeDirectories
    $generatorArguments = @(
        "--manifest", $script:IdentityManifest,
        "--env-file", $script:IdentityEnvironmentFile,
        "--output", $script:IdentityRealmOutput,
        "--connection-output", $script:IdentityConnectionProfile
    )
    if (Test-Path -LiteralPath $script:IdentityConfigurationSettings -PathType Leaf) {
        $generatorArguments += @("--settings-file", $script:IdentityConfigurationSettings)
    }
    if (Test-Path -LiteralPath $script:IdentityUserOverlay -PathType Leaf) {
        $generatorArguments += @("--users-file", $script:IdentityUserOverlay)
    }
    if (Test-Path -LiteralPath $script:IdentityGroupOverlay -PathType Leaf) {
        $generatorArguments += @("--groups-file", $script:IdentityGroupOverlay)
    }
    if (Test-Path -LiteralPath $script:IdentityOidcSettings -PathType Leaf) {
        $generatorArguments += @("--oidc-settings-file", $script:IdentityOidcSettings)
    }
    if (Test-Path -LiteralPath $script:IdentitySamlSettings -PathType Leaf) {
        $generatorArguments += @(
            "--saml-settings-file", $script:IdentitySamlSettings,
            "--saml-certificate-file", $script:IdentitySaml2IntCertificate
        )
    }
    & python $script:IdentityRealmGenerator @generatorArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Northlake realm generation failed with exit code $LASTEXITCODE."
    }
    if (Test-Path -LiteralPath $script:IdentityScenarioSettings -PathType Leaf) {
        $scenarioArguments = @(
            "--settings-file", $script:IdentityScenarioSettings,
            "--env-file", $script:IdentityEnvironmentFile,
            "--manifest", $script:IdentityManifest,
            "--realm-output-directory", $script:IdentityImportDirectory,
            "--connection-output-directory", $script:IdentityScenarioConnectionDirectory
        )
        if (Test-Path -LiteralPath $script:IdentityUserOverlay -PathType Leaf) {
            $scenarioArguments += @("--user-overlay", $script:IdentityUserOverlay)
        }
        if (Test-Path -LiteralPath $script:IdentityGroupOverlay -PathType Leaf) {
            $scenarioArguments += @("--group-overlay", $script:IdentityGroupOverlay)
        }
        & python $script:IdentityScenarioModel @scenarioArguments
        if ($LASTEXITCODE -ne 0) {
            throw "Northlake two-realm scenario generation failed with exit code $LASTEXITCODE."
        }
    }
}

function Copy-IdentityRootCertificate {
    New-IdentityRuntimeDirectories
    $containerIds = @(& docker ps `
        --filter "label=com.docker.compose.project=$script:IdentityComposeProject" `
        --filter "label=com.docker.compose.service=caddy" `
        --format "{{.ID}}")
    if ($LASTEXITCODE -ne 0 -or $containerIds.Count -ne 1) {
        throw "Unable to resolve the running Caddy container."
    }
    $containerId = $containerIds[0]

    $labels = & docker inspect $containerId `
        --format "{{index .Config.Labels `"com.docker.compose.project`"}}|{{index .Config.Labels `"com.docker.compose.service`"}}"
    if ($LASTEXITCODE -ne 0 -or $labels -ne "$($script:IdentityComposeProject)|caddy") {
        throw "Refusing to copy the root certificate because Caddy ownership labels did not match."
    }

    for ($attempt = 1; $attempt -le 15; $attempt++) {
        & docker cp `
            "${containerId}:/data/caddy/pki/authorities/local/root.crt" `
            $script:IdentityRootCertificate *> $null
        if ($LASTEXITCODE -eq 0) {
            return $script:IdentityRootCertificate
        }
        Start-Sleep -Seconds 1
    }
    throw "Unable to copy Caddy's local root certificate from the running container."
}
