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

# Haal alle geldige tags op en zoek de nieuwste
$tags = git tag | Where-Object { $_ -match "^$tagPrefix\d+\.\d+\.\d+$" } | Sort-Object {
    $version = $_ -replace "^$tagPrefix", ""
    [Version]::new(($version -split "\.")[0], ($version -split "\.")[1], ($version -split "\.")[2])
} -Descending

# Als er geen tags zijn, starten we met versie v0.0.1
if (-not $tags) {
    Write-Warning "Geen tags gevonden. Start met versie v0.0.1"
    $newVersion = "0.0.1"
    $releaseNotes = "Initial release"
} else {
    # Laatste en op één na laatste tags
    $latestTag = $tags[0]
    $previousTag = $tags[1]

    Write-Host "Vorige tag: $previousTag → Laatste tag: $latestTag"

    # Haal commit messages op tussen vorige en laatste tag
    $range = "$previousTag..$latestTag"
    $rawLog = & git log --pretty=%s $range

    $commitMessages = $rawLog -split "`r?`n" | Where-Object { $_.Trim() -ne "" }

    if ($commitMessages.Count -eq 0) {
        Write-Host "Geen nieuwe commits sinds $previousTag" -ForegroundColor Yellow
        exit 0
    }

    $newVersion = ($latestTag -replace "^$tagPrefix", "") # De versie bepalen door de laatste tag
    $releaseNotes = "Release Notes voor $newVersion`n`nChanges:`n- " + ($commitMessages -join "`n- ")
    Write-Host "`n$releaseNotes" -ForegroundColor Cyan
}

# Maak de nieuwe tag aan
$newTag = "$tagPrefix$newVersion"
Write-Host "Nieuwe tag aanmaken: $newTag"

if (git tag | Select-String "^$newTag$") {
    Write-Error "Tag $newTag bestaat al! Gebruik 'git tag -d $newTag' om lokaal te verwijderen en 'git push $remote :refs/tags/$newTag' om remote te verwijderen."
    exit 1
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
