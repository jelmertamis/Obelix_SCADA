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

# Controleer of de huidige commit al getagd is
$currentTags = git tag --points-at $currentCommit | Where-Object { $_ -match "^$tagPrefix\d+\.\d+\.\d+$" } | Sort-Object {
    $version = $_ -replace "^$tagPrefix", ""
    [Version]::new(($version -split "\.")[0], ($version -split "\.")[1], ($version -split "\.")[2])
} -Descending

if ($currentTags) {
    $currentVersion = $currentTags | Select-Object -First 1
    Write-Host "Huidige commit heeft versie: $currentVersion" -ForegroundColor Cyan
    if ($currentTags.Count -gt 1) {
        Write-Warning "Meerdere tags ($($currentTags -join ', ')) wijzen naar dezelfde commit. Overweeg oudere tags te verwijderen."
        $response = Read-Host "Wil je alle tags behalve de nieuwste ($currentVersion) verwijderen? (y/n)"
        if ($response -eq 'y') {
            $tagsToDelete = $currentTags | Where-Object { $_ -ne $currentVersion }
            foreach ($tag in $tagsToDelete) {
                Write-Host "Verwijder tag: $tag"
                git tag -d $tag
                git push $remote :refs/tags/$tag
            }
            Write-Host "Alleen tag $currentVersion behouden." -ForegroundColor Green
        }
    }
} else {
    Write-Host "Huidige commit heeft geen versie (geen tag)." -ForegroundColor Yellow
}

# Haal alle geldige tags op en zoek de nieuwste
$tags = git tag | Where-Object { $_ -match "^$tagPrefix\d+\.\d+\.\d+$" } | Sort-Object {
    $version = $_ -replace "^$tagPrefix", ""
    [Version]::new(($version -split "\.")[0], ($version -split "\.")[1], ($version -split "\.")[2])
} -Descending

if (-not $tags) {
    Write-Warning "Geen tags gevonden. Start met versie v0.0.1"
    $newVersion = "0.0.1"
    $releaseNotes = "Initial release"
} else {
    $latestTag = $tags | Select-Object -First 1
    $latestTagCommit = git rev-list -n 1 $latestTag
    Write-Host "Nieuwste tag: $latestTag (commit: $latestTagCommit)"

    if ($latestTagCommit -eq $currentCommit) {
        Write-Host "Geen nieuwe commits sinds de laatste tag ($latestTag). Script wordt afgesloten." -ForegroundColor Yellow
        exit 0
    }

    # Bepaal nieuwe patchversie
    $versionNumber = $latestTag -replace "^$tagPrefix", ""
    $versionParts = $versionNumber -split "\."
    $major = [int]$versionParts[0]
    $minor = [int]$versionParts[1]
    $patch = [int]$versionParts[2]
    $patch += 1
    $newVersion = "$major.$minor.$patch"

    # Genereer release notes — forceer altijd array
    $commitMessages = @(git log --pretty=%s $latestTag..HEAD)
    if ($commitMessages.Count -gt 0) {
        $releaseNotes = "Release Notes for $newVersion`n`nChanges:`n- " + ($commitMessages -join "`n- ")
    } else {
        $releaseNotes = "Release Notes for $newVersion`n`nNo detailed commit messages available."
    }

    Write-Host "Release Notes:`n$releaseNotes" -ForegroundColor Cyan
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
