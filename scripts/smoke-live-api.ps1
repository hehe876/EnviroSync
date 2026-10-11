# OPT-IN: makes live S3 GET requests via the local FastAPI server.
# It creates or changes no S3 resources. AWS GET costs may apply.
$ErrorActionPreference = "Stop"
$api = "http://127.0.0.1:8000"
Write-Host "Verifying existing API and published data (this makes S3 reads; applicable AWS charges may apply)..."
$health = Invoke-RestMethod "$api/api/health"
if ($health.status -ne "ok") { throw "FastAPI is unavailable" }
$catalog = Invoke-RestMethod "$api/api/datasets"
$datasets = @($catalog.datasets)
if ($datasets.Count -lt 2) { throw "Fewer than two catalog datasets are available: Milestone 1B federation is not ready" }
$left = $datasets[0]
$right = $datasets[1]
if ($left.aws_region -eq $right.aws_region) { throw "Selected datasets are not from different AWS regions" }
$latestStart = @($left.start_date, $right.start_date) | Sort-Object | Select-Object -Last 1
$earliestEnd = @($left.end_date, $right.end_date) | Sort-Object | Select-Object -First 1
if ($latestStart -gt $earliestEnd) { throw "Published datasets do not have overlapping calendar dates" }
$finalDate = [datetime]::ParseExact($earliestEnd, "yyyy-MM-dd", [cultureinfo]::InvariantCulture)
$beginDate = $finalDate.AddDays(-2)
$begin = $beginDate.ToString("yyyy-MM-dd")
if ($begin -lt $latestStart) { $begin = $latestStart }
$c1 = [uri]::EscapeDataString($left.city)
$c2 = [uri]::EscapeDataString($right.city)
$range = "start=$begin&end=$earliestEnd"
$observations = Invoke-RestMethod "$api/api/observations?city=$c1&$range"
if ($observations.row_count -lt 1 -or $observations.sha256_verified -ne $true) {
    throw "Milestone 1B primary-city observations are missing or failed SHA-256 verification"
}
$comparison = Invoke-RestMethod "$api/api/compare?city1=$c1&city2=$c2&$range&metric=temp_max_c"
if (@($comparison.points).Count -lt 1) { throw "Milestone 2 comparison has no aligned points" }
$src1 = $comparison.sources.PSObject.Properties[$left.city].Value
$src2 = $comparison.sources.PSObject.Properties[$right.city].Value
if ($src1.sha256_verified -ne $true -or $src2.sha256_verified -ne $true) {
    throw "Cross-region S3 retrieval is not SHA-256 verified"
}
Write-Host "PASS: health + catalog + regional observations + SHA-256 verified cross-region comparison."
Write-Host "Region 1: $($left.city) ($($left.aws_region)); Region 2: $($right.city) ($($right.aws_region)); dates: $begin to $earliestEnd"
