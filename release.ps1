# release.ps1

# Configuratie
$branch = "dev"
$remote = "origin"
$tagPrefix = "v"

# Controleer of we op de juiste branch zitten
$currentBranch = git rev-parse --abbrev-ref HEAD
if ($currentBranch -ne $branch) {
    Write-Error "Je bent niet op de '$branch' branch. Huidige branch: $currentBranch"
    exit 1
}

# Synchroniseer tags met remote
Write-Host "Synchroniseer tags met $remote..."
git fetch $remote --tags

# Haal de huidige commit op
$currentCommit = git rev-parse HEAD
Write-Host "Huidige commit: $currentCommit"

# Haal de laatste tag op
$tags = git tag | Where-Object { $_ -match "^$tagPrefix\d+\.\d+\.\d+$" } | Sort-Object {
    $version = $_ -replace "^$tagPrefix", ""
    [Version]::new(($version -split "\.")[0], ($version -split "\.")[1], ($version -split "\.")[2])
} -Descending

if (-not $tags) {
    Write-Warning "Geen tags gevonden. Start met versie v0.0.1"
    $newVersion = "0.0.1"
    $releaseNotes = "Initial release"
} else {
    $latestTag = $tags[0]
    Write-Host "Laatste tag: $latestTag"

    # Haal commit messages op tussen de laatste tag en de huidige commit (HEAD)
    $range = "$latestTag..$currentCommit"
    $rawLog = & git log --pretty=%s $range
    $commitMessages = $rawLog -split "`r?`n" | Where-Object { $_.Trim() -ne "" }

    if ($commitMessages.Count -eq 0) {
        Write-Host "Geen nieuwe commits sinds $latestTag" -ForegroundColor Yellow
        exit 0
    }

    # Haal versie-informatie op uit de laatste tag
    $versionParts = ($latestTag -replace "^$tagPrefix", "") -split "\."
    $major = [int]$versionParts[0]
    $minor = [int]$versionParts[1]
    $patch = [int]$versionParts[2]

    # Verhoog de patchversie
    $patch += 1
    $newVersion = "$major.$minor.$patch"

    # Maak release notes
    $releaseNotes = "Release Notes voor $newVersion`n`nChanges:`n- " + ($commitMessages -join "`n- ")
    Write-Host "`n$releaseNotes" -ForegroundColor Cyan
}

# Maak de nieuwe tag aan
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
