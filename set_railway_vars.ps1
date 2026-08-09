$envFile = "backend\.env"
$vars = @{}
foreach ($line in Get-Content $envFile) {
    if ($line -match '^([^#][^=]*)=(.*)$') {
        $key = $matches[1].Trim()
        $val = $matches[2].Trim()
        $vars[$key] = $val
    }
}

foreach ($key in $vars.Keys) {
    $val = $vars[$key]
    $arg = "$key=$val"
    railway variables --service image set $arg 2>&1 | Out-Null
    Write-Host "Set: $key"
}

# Set additional production vars not in .env
railway variables --service image set "GROQ_VISION_MODEL=qwen/qwen3.6-27b" 2>&1 | Out-Null
Write-Host "Set: GROQ_VISION_MODEL"
railway variables --service image set "GROQ_MAX_CONCURRENCY=4" 2>&1 | Out-Null
Write-Host "Set: GROQ_MAX_CONCURRENCY"
railway variables --service image set "SIMILARITY_THRESHOLD=0.90" 2>&1 | Out-Null
Write-Host "Set: SIMILARITY_THRESHOLD"

Write-Host "Done. All env vars configured."
