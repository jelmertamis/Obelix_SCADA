$previousTag = "v0.0.8"
$range = "$previousTag..HEAD"
$rawLog = & git log --pretty=%s $range

Write-Host "`n--- RAW LOG OUTPUT ---"
Write-Host $rawLog
Write-Host "--- END ---`n"

$commitMessages = $rawLog -split "`r?`n" | Where-Object { $_.Trim() -ne "" }

if ($commitMessages.Count -eq 0) {
    Write-Host "Geen nieuwe commits sinds $previousTag" -ForegroundColor Yellow
} else {
    $releaseNotes = "Release Notes sinds ${previousTag}`n`nChanges:`n- " + ($commitMessages -join "`n- ")
    Write-Host $releaseNotes -ForegroundColor Cyan
}
