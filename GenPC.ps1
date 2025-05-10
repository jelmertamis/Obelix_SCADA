# Filename: Generate-ProjectCode.ps1

# Step 0: Define output file and prompt file
$OutputFile = "project_code.txt"
$PromptFile = "prompt.md"

# Step 1: Determine version from latest Git tag and previous project_code.txt
$Version = "0.0.0.1"  # Default fallback
$BaseVersion = "0.0.0"
$Minor = 1

$GitTag = git describe --tags --abbrev=0 2>$null
if ($GitTag) {
    $BaseVersion = $GitTag.Trim()
    $Version = "$BaseVersion.$Minor"

    if (Test-Path $OutputFile) {
        Write-Host "Checking existing project_code.txt for previous version..." -ForegroundColor Cyan
        $Content = Get-Content $OutputFile -ErrorAction SilentlyContinue
        $VersionLine = $Content | Where-Object { $_ -match "^Versie: $BaseVersion\.(\d+)$" } | Select-Object -First 1
        if ($VersionLine) {
            $PreviousMinor = [regex]::Match($VersionLine, "$BaseVersion\.(\d+)").Groups[1].Value
            $Minor = [int]$PreviousMinor + 1
            $Version = "$BaseVersion.$Minor"
            Write-Host "Found previous base version, incrementing to: $Version" -ForegroundColor Green
        } else {
            Write-Host "New base version detected: $BaseVersion. Starting with .$Minor" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "No Git tags found. Using fallback version: $Version" -ForegroundColor Red
}

# Step 2: Delete existing project_code.txt if it exists
if (Test-Path $OutputFile) {
    Write-Host "Removing existing project_code.txt..." -ForegroundColor Yellow
    Remove-Item $OutputFile -Force
}

# Step 3: Add project description header
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
@"
Obelix_SCADA: Projectbeschrijving & Samenwerkingsrichtlijn
Versie: $Version
Laatste update: $Timestamp

"@ | Out-File $OutputFile -Encoding UTF8

# Step 4: If prompt.md exists, append its contents
if (Test-Path $PromptFile) {
    Write-Host "Including prompt.md..." -ForegroundColor Cyan
    Get-Content $PromptFile | Out-File $OutputFile -Append -Encoding UTF8
    "" | Out-File $OutputFile -Append -Encoding UTF8
}

# Step 5: Append timestamp and Git info
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

# Step 6: Find matching files and process them
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
