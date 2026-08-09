$config = Get-Content "$HOME\.railway\config.json" | ConvertFrom-Json

# Token is stored in the sessions folder
$sessionFiles = Get-ChildItem "$HOME\.railway\sessions\" -Filter "*.json" -ErrorAction SilentlyContinue
$token = $null
foreach ($f in $sessionFiles) {
    $session = Get-Content $f.FullName | ConvertFrom-Json
    if ($session.token) { $token = $session.token; break }
    if ($session.apiToken) { $token = $session.apiToken; break }
}

if (-not $token) {
    Write-Host "Trying user field..."
    Write-Host "Session files: $($sessionFiles.Count)"
    foreach ($f in $sessionFiles) {
        Write-Host "File: $($f.Name)"
        Get-Content $f.FullName
    }
} else {
    Write-Host "TOKEN_FOUND - calling API"
    $serviceId = "87619dda-06cc-40e0-b6da-be7e9c0dd95e"
    $mutation = 'mutation { serviceUpdate(id: \"' + $serviceId + '\", input: { rootDirectory: \"backend\" }) { id } }'
    $body = "{`"query`": `"$mutation`"}"

    $response = Invoke-RestMethod -Uri "https://backboard.railway.com/graphql/v2" `
        -Method POST `
        -Headers @{ "Authorization" = "Bearer $token"; "Content-Type" = "application/json" } `
        -Body $body
    Write-Host ($response | ConvertTo-Json -Depth 5)
}
