# Filename: Generate-ProjectCode.ps1

# Step 0: Define output file and optional prompt file
$OutputFile = "project_code.txt"
$PromptFile  = "prompt.md"

# Step 1: Delete existing project_code.txt if it exists
test-path $OutputFile | ForEach-Object {
    Write-Host "Removing existing project_code.txt..." -ForegroundColor Yellow
    Remove-Item $OutputFile -Force
}

# Step 1.1: If prompt.md exists, prepend its contents
if (Test-Path $PromptFile) {
    Write-Host "Including prompt.md at the beginning..." -ForegroundColor Cyan
    Get-Content $PromptFile | Out-File $OutputFile -Encoding UTF8
    # Add a blank line separator
    "" | Out-File $OutputFile -Append -Encoding UTF8
}

# Step 2: Create new file with timestamp and Git info (appended)
$Timestamp   = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$GitCommit   = git rev-parse HEAD 2>$null
$GitBranch   = git rev-parse --abbrev-ref HEAD 2>$null
$GitMessage  = git log -1 --pretty=%B 2>$null
$GitStatus   = git status --porcelain 2>$null

if (-not $GitCommit) {
    $GitCommit   = "N/A (not a Git repo or Git not installed)"
    $GitBranch   = "N/A"
    $GitMessage  = "N/A"
    $GitStatus   = @()
}

"# Generated on $Timestamp"            | Out-File $OutputFile -Append -Encoding UTF8
"# Git branch: $GitBranch"            | Out-File $OutputFile -Append -Encoding UTF8
"# Git commit: $GitCommit"            | Out-File $OutputFile -Append -Encoding UTF8
"# Commit message: $GitMessage"       | Out-File $OutputFile -Append -Encoding UTF8

if ($GitStatus.Count -gt 0) {
    "# ⚠️ Uncommitted changes present:"   | Out-File $OutputFile -Append -Encoding UTF8
    foreach ($Line in $GitStatus) {
        "#   $Line"                     | Out-File $OutputFile -Append -Encoding UTF8
    }
} else {
    "# No uncommitted changes."         | Out-File $OutputFile -Append -Encoding UTF8
}

"" | Out-File $OutputFile -Append -Encoding UTF8

Write-Host "Starting file aggregation..." -ForegroundColor Cyan

# Step 3: Find matching files and process them
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
