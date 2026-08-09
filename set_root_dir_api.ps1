$token = "XCU5fxkRabTbZFiGFzry3pJJO1He76Y3oZxqBhXC4eY"
$serviceId = "87619dda-06cc-40e0-b6da-be7e9c0dd95e"

# The input structure for serviceUpdate might require source
$mutation = 'mutation { serviceUpdate(id: \"' + $serviceId + '\", input: { source: { rootDirectory: \"/backend\" } }) { id } }'
$body = "{`"query`": `"$mutation`"}"

$response = Invoke-RestMethod -Uri "https://backboard.railway.com/graphql/v2" `
    -Method POST `
    -Headers @{ "Authorization" = "Bearer $token"; "Content-Type" = "application/json" } `
    -Body $body

Write-Host "Response 1:"
Write-Host ($response | ConvertTo-Json -Depth 5)

$mutation2 = 'mutation { serviceUpdate(id: \"' + $serviceId + '\", input: { rootDirectory: \"/backend\" }) { id } }'
$body2 = "{`"query`": `"$mutation2`"}"

$response2 = Invoke-RestMethod -Uri "https://backboard.railway.com/graphql/v2" `
    -Method POST `
    -Headers @{ "Authorization" = "Bearer $token"; "Content-Type" = "application/json" } `
    -Body $body2 -ErrorAction SilentlyContinue

Write-Host "Response 2:"
Write-Host ($response2 | ConvertTo-Json -Depth 5)
