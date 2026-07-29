Set-StrictMode -Version Latest

$script:IdentityRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$script:RepositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $script:IdentityRoot ".."))
$script:IdentityComposeFile = Join-Path $script:IdentityRoot "compose.yml"
$script:IdentityEnvironmentFile = Join-Path $script:IdentityRoot ".env"
$script:IdentityRuntimeDirectory = Join-Path $script:IdentityRoot ".runtime"
$script:IdentityImportDirectory = Join-Path $script:IdentityRuntimeDirectory "import"
$script:IdentityConnectionProfile = Join-Path $script:IdentityRuntimeDirectory "connection.json"
$script:IdentityCertificateDirectory = Join-Path $script:IdentityRuntimeDirectory "certs"
$script:IdentityRootCertificate = Join-Path $script:IdentityCertificateDirectory "caddy-local-root.crt"
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
    return $values
}

function Invoke-IdentityCompose {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]] $ArgumentList
    )

    & docker compose `
        --project-directory $script:IdentityRoot `
        --env-file $script:IdentityEnvironmentFile `
        --file $script:IdentityComposeFile `
        @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed with exit code $LASTEXITCODE."
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
    & python $script:IdentityRealmGenerator `
        --manifest $script:IdentityManifest `
        --env-file $script:IdentityEnvironmentFile `
        --output $script:IdentityRealmOutput `
        --connection-output $script:IdentityConnectionProfile
    if ($LASTEXITCODE -ne 0) {
        throw "Northlake realm generation failed with exit code $LASTEXITCODE."
    }
}

function Copy-IdentityRootCertificate {
    New-IdentityRuntimeDirectories
    & docker compose `
        --project-directory $script:IdentityRoot `
        --env-file $script:IdentityEnvironmentFile `
        --file $script:IdentityComposeFile `
        cp "caddy:/data/caddy/pki/authorities/local/root.crt" $script:IdentityRootCertificate *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to copy Caddy's local root certificate from the running container."
    }
    return $script:IdentityRootCertificate
}
