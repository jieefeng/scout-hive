Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -like '*uvicorn*' -or $_.CommandLine -like '*app.main*'
} | ForEach-Object {
    Write-Host "Killing PID $($_.ProcessId): $($_.CommandLine)"
    Stop-Process -Id $_.ProcessId -Force
}
Write-Host "Done"