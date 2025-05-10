# Configuratie
$branch = "dev"
$remote = "origin"
$tagPrefix = "v"
$changelogFile = "CHANGELOG.md"
$releaseDir = "releases"

# Zorg dat releases-map bestaat
if (-not (Test-Path $releaseDir)) {
    New-Item -ItemType Directory -Path $releaseDir | Out-Null
}

# Controleer branch
$currentBranch = git rev-parse --abbrev-ref HEAD
if ($currentBranch -ne $branch) {
    Write-Error "Je bent niet op de '$branch' branch. Huidige branch: $currentBranch"
    exit 1
}

# Synchroniseer tags
Write-Host "Synchroniseer tags met $remote..."
git fetch $remote --tags

# Haal huidige commit
$currentCommit = git rev-parse HEAD
Write-Host "Huidige commit: $currentCommit"

# Laatste tag bepalen
$tags = git tag | Where-Object { $_ -match "^$tagPrefix\d+\.\d+\.\d+$" } | Sort-Object {
    $version = $_ -replace "^$tagPrefix", ""
    [Version]::new(($version -split "\.")[0], ($version -split "\.")[1], ($version -split "\.")[2])
} -Descending

if (-not $tags) {
    Write-Warning "Geen tags gevonden. Start met versie v0.0.1"
    $newVersion = "0.0.1"
    $releaseNotes = "Initial release"
    $commitMessages = @("Initial commit")
} else {
    $latestTag = $tags[0]
    Write-Host "Laatste tag: $latestTag"

    $range = "$latestTag..$currentCommit"
    $rawLog = & git log --pretty=%s $range
    $commitMessages = $rawLog -split "`r?`n" | Where-Object { $_.Trim() -ne "" }

    if ($commitMessages.Count -eq 0) {
        Write-Host "Geen nieuwe commits sinds $latestTag" -ForegroundColor Yellow
        exit 0
    }

    $versionParts = ($latestTag -replace "^$tagPrefix", "") -split "\."
    $major = [int]$versionParts[0]
    $minor = [int]$versionParts[1]
    $patch = [int]$versionParts[2] + 1
    $newVersion = "$major.$minor.$patch"

    $releaseNotes = "Release Notes voor $newVersion`n`nChanges:`n- " + ($commitMessages -join "`n- ")
    Write-Host "`n$releaseNotes" -ForegroundColor Cyan
}

$newTag = "$tagPrefix$newVersion"
Write-Host "Nieuwe tag aanmaken: $newTag"

if (git tag | Select-String "^$newTag$") {
    Write-Host "Tag $newTag bestaat al. Verwijderen en opnieuw aanmaken..."
    git tag -d $newTag
    git push $remote :refs/tags/$newTag
}

try {
    git tag -a $newTag -m $releaseNotes
    git push $remote $branch
    git push $remote $newTag
    Write-Host "Release $newTag succesvol aangemaakt en gepusht naar $remote." -ForegroundColor Green
} catch {
    Write-Error "Fout bij het aanmaken of pushen van de tag: $_"
    exit 1
}

# 🎯 Schrijf release notes naar los bestand
$releaseFile = Join-Path $releaseDir "release-$newTag.md"
@"
# Release $newTag

$releaseNotes
"@ | Out-File $releaseFile -Encoding UTF8

Write-Host "Release notes opgeslagen naar $releaseFile" -ForegroundColor Cyan

# 📘 Update of create CHANGELOG.md
$timestamp = Get-Date -Format "yyyy-MM-dd"
$changelogEntry = @"
## [$newTag] - $timestamp

- $($commitMessages -join "`n- ")
"@

if (Test-Path $changelogFile) {
    # Voeg bovenaan toe
    $existing = Get-Content $changelogFile
    @($changelogEntry, "", $existing) | Set-Content $changelogFile -Encoding UTF8
} else {
    # Nieuw bestand
    @(
        "# Changelog",
        "",
        $changelogEntry
    ) | Set-Content $changelogFile -Encoding UTF8
}

Write-Host "CHANGELOG.md bijgewerkt." -ForegroundColor Green
