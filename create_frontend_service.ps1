$config = Get-Content "$HOME\.railway\config.json" | ConvertFrom-Json
$token = $config.user.accessToken
$projectId = "edd452c7-0240-43f0-a107-a60a6b94b5cc"

$mutation = 'mutation { serviceCreate(input: { projectId: \"' + $projectId + '\", name: \"frontend\" }) { id } }'
$body = "{`"query`": `"$mutation`"}"

$response = Invoke-RestMethod -Uri "https://backboard.railway.com/graphql/v2" `
    -Method POST `
    -Headers @{ "Authorization" = "Bearer $token"; "Content-Type" = "application/json" } `
    -Body $body
Write-Host ($response | ConvertTo-Json -Depth 5)
