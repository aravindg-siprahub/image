$token = 'XCU5fxkRabTbZFiGFzry3pJJO1He76Y3oZxqBhXC4eY'
$query = 'mutation { projectTriggerLatestDeployment(projectId: \"edd452c7-0240-43f0-a107-a60a6b94b5cc\", environmentId: \"651fae8a-c292-4e3a-9a78-366d2e5ec895\") }'
$body = "{`"query`": `"$query`"}"
Invoke-RestMethod -Uri 'https://backboard.railway.com/graphql/v2' -Method POST -Headers @{ 'Authorization' = "Bearer $token"; 'Content-Type' = 'application/json' } -Body $body
