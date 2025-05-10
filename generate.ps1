# Gecombineerd script voor versiebeheer, release en projectcode

# Configuratie
$branch = "dev"
$remote = "origin"
$tagPrefix = "v"
$VersionFilePath = "project_code.txt"  # Bestand voor de versie-informatie
$PromptFile = "prompt.md"
$OutputFile = "project_code.txt"

# Stap 1: Lees het huidige versienummer uit project_code.txt
$Version = "v0.0.1"  # Default versie
if (Test-Path $VersionFilePath) {
    Write-Host "Lezen van versie uit project_code.txt..." -ForegroundColor Cyan
    $Content = Get-Content $VersionFilePath -ErrorAction SilentlyContinue
    $VersionLine = $Content | Where-Object { $_ -match "^Versie: \d+\.\d+$" } | Select-Object -First 1
    if ($VersionLine) {
        # Versie extraheren (bijv. "1.0" uit "Versie: 1.0")
        $Version = $VersionLine -replace "^Versie: (\d+\.\d+)$", '$1'
        Write-Host "Gevonden versie: $Version" -ForegroundColor Green
    } else {
        Write-Host "Geen versie gevonden in project_code.txt. Gebruik default versie: $Version" -ForegroundColor Yellow
    }
}

# Stap 2: Verhoog de versie
$VersionParts = $Version.Split('.')
$Major = [int]$VersionParts[0]
$Minor = [int]$VersionParts[1]
$Patch = [int]$VersionParts[2]

# Verhoog patchversie
$Patch += 1
$NewVersion = "$Major.$Minor.$Patch"

# Stap 3: Verhoog de versie in project_code.txt
Write-Host "Verhoogde versie: $NewVersion" -ForegroundColor Green
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# Voeg de nieuwe versie toe aan project_code.txt
@"
Obelix_SCADA: Projectbeschrijving & Samenwerkingsrichtlijn
Versie: $NewVersion
Laatste update: $Timestamp
"@ | Out-File $OutputFile -Encoding UTF8

# Stap 4: Als prompt.md bestaat, voeg de inhoud toe
if (Test-Path $PromptFile) {
    Write-Host "Including prompt.md..." -ForegroundColor Cyan
    Get-Content $PromptFile | Out-File $OutputFile -Append -Encoding UTF8
    "" | Out-File $OutputFile -Append -Encoding UTF8
}

# Stap 5: Voeg Git-informatie toe
$GitCommit = git rev-parse HEAD 2>$null
$GitBranch = git rev-parse --abbrev-ref HEAD 2>$null
$GitMessage = git log -1 --pretty=%B 2>$null
$GitStatus = git status --porcelain 2>$null

if (-not $GitCommit) {
    $GitCommit = "N/A (not a Git repo or Git not installed)"
    $GitBranch = "N/A"
    $GitMessage = "N/A"
    $GitStatus = @()
}

"# Generated on $Timestamp" | Out-File $OutputFile -Append -Encoding UTF8
"# Git branch: $GitBranch" | Out-File $OutputFile -Append -Encoding UTF8
"# Git commit: $GitCommit" | Out-File $OutputFile -Append -Encoding UTF8
"# Commit message: $GitMessage" | Out-File $OutputFile -Append -Encoding UTF8

if ($GitStatus.Count -gt 0) {
    "# ⚠️ Uncommitted changes present:" | Out-File $OutputFile -Append -Encoding UTF8
    foreach ($Line in $GitStatus) {
        "#   $Line" | Out-File $OutputFile -Append -Encoding UTF8
    }
} else {
    "# No uncommitted changes." | Out-File $OutputFile -Append -Encoding UTF8
}

"" | Out-File $OutputFile -Append -Encoding UTF8

Write-Host "Starting file aggregation..." -ForegroundColor Cyan

# Stap 6: Zoek en verwerk alle bestanden
$Files = Get-ChildItem -Recurse -Include *.py,*.html,*.js,*.css -Exclude settings.db |
    Where-Object { $_.FullName -notlike "*\Obelix_SCADA_venv\*" }

if ($Files.Count -eq 0) {
    Write-Host "No matching files found." -ForegroundColor Red
} else {
    foreach ($File in $Files) {
        Write-Host "Processing file: $($File.FullName)" -ForegroundColor Green
        "===== $($File.FullName) =====" | Out-File $OutputFile -Append -Encoding UTF8
        Get-Content $File.FullName | Out-File $OutputFile -Append -Encoding UTF8
    }
    Write-Host "✅ All files processed successfully. Output saved to $OutputFile" -ForegroundColor Green
}

# Stap 7: Synchroniseer tags met remote en verhoog versie
Write-Host "Synchroniseer tags met $remote..."
git fetch $remote --tags

# Haal de laatste tag op en verhoog versie
$tags = git tag | Where-Object { $_ -match "^$tagPrefix\d+\.\d+\.\d+$" } | Sort-Object {
    $version = $_ -replace "^$tagPrefix", ""
    [Version]::new(($version -split "\.")[0], ($version -split "\.")[1], ($version -split "\.")[2])
} -Descending

if (-not $tags) {
    Write-Warning "Geen tags gevonden. Start met versie v0.0.1"
    $NewVersion = "0.0.1"
    $ReleaseNotes = "Initial release"
} else {
    $latestTag = $tags[0]
    Write-Host "Laatste tag: $latestTag"

    # Haal commit messages op tussen de laatste tag en de huidige commit (HEAD)
    $range = "$latestTag..HEAD"
    $rawLog = & git log --pretty=%s $range
    $commitMessages = $rawLog -split "`r?`n" | Where-Object { $_.Trim() -ne "" }

    if ($commitMessages.Count -eq 0) {
        Write-Host "Geen nieuwe commits sinds $latestTag" -ForegroundColor Yellow
        exit 0
    }

    # Maak release notes
    $ReleaseNotes = "Release Notes voor $NewVersion`n`nChanges:`n- " + ($commitMessages -join "`n- ")
    Write-Host "`n$ReleaseNotes" -ForegroundColor Cyan
}

# Maak de nieuwe tag aan
$NewTag = "$tagPrefix$NewVersion"
Write-Host "Nieuwe tag aanmaken: $NewTag"

if (git tag | Select-String "^$NewTag$") {
    Write-Host "Tag $NewTag bestaat al. Verwijderen en opnieuw aanmaken..."
    git tag -d $NewTag
    git push $remote :refs/tags/$NewTag
}

# Stap 8: Maak de nieuwe tag en release notes aan
try {
    git tag -a $NewTag -m $ReleaseNotes
    git push $remote $branch
    git push $remote $NewTag
    Write-Host "Release $NewTag succesvol aangemaakt en gepusht naar $remote." -ForegroundColor Green
} catch {
    Write-Error "Fout bij het aanmaken of pushen van de tag: $_"
    exit 1
}
