<#
Register-Webhooks.ps1

Helper to automate:
 - install ngrok authtoken (optional)
 - start ngrok (background)
 - discover public https URL
 - register Telegram webhook
 - register Twilio (WhatsApp) incoming webhook (if possible)
 - run basic verification tests (health, dry-run webhook posts, optionally send a test WhatsApp via Twilio)
 - cleanup (stop ngrok & unset temp env vars)

Usage examples:
  # Use env vars already set in your shell
  .\scripts\register_webhooks.ps1

  # Pass tokens explicitly for this run
  .\scripts\register_webhooks.ps1 -NgrokAuthtoken "xxxx" -TwilioSid "ACxxx" -TwilioAuth "yyy" -TelegramToken "830..." -WhatsappNumber "whatsapp:+254758577236"

Notes:
 - This script prefers values from parameters then falls back to environment variables.
 - It will not commit or persist secrets to the repository.
 - If your Python webhook server is not running it will offer to start it for you (requires you have a shell where starting is possible).
#>

param(
    [string]$NgrokAuthtoken,
    [string]$TwilioSid,
    [string]$TwilioAuth,
    [string]$TelegramToken,
    [string]$WhatsappNumber = "whatsapp:+254758577236",
    [switch]$StartServer,
    [switch]$SendInboundTestMessages
)

function Get-EnvOrParam($paramValue, $envName) {
    if ($paramValue) { return $paramValue }
    $envValue = ${env:$envName}
    if ($envValue) { return $envValue }
    return $null
}

$NgrokAuthtoken = Get-EnvOrParam -paramValue $NgrokAuthtoken -envName 'NGROK_AUTHTOKEN'
$TwilioSid = Get-EnvOrParam -paramValue $TwilioSid -envName 'TWILIO_ACCOUNT_SID'
$TwilioAuth = Get-EnvOrParam -paramValue $TwilioAuth -envName 'TWILIO_AUTH_TOKEN'
$TelegramToken = Get-EnvOrParam -paramValue $TelegramToken -envName 'TELEGRAM_TOKEN'
$WhatsappNumber = Get-EnvOrParam -paramValue $WhatsappNumber -envName 'TWILIO_WHATSAPP_NUMBER'

Write-Host "Starting webhook registration helper..." -ForegroundColor Cyan

# 1) Ensure the Flask server is running
$healthUrl = 'http://127.0.0.1:5000/health'
try {
    $r = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    Write-Host "Local webhook server healthy: $($r.StatusCode)" -ForegroundColor Green
} catch {
    Write-Warning "Local webhook server not reachable at $healthUrl."
    if ($StartServer) {
        Write-Host "Attempting to start the server (python app.py) in a new background process..." -ForegroundColor Yellow
        Start-Process -FilePath 'python' -ArgumentList 'app.py' -WindowStyle Hidden
        Start-Sleep -Seconds 2
        try { Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop; Write-Host 'Server started and healthy' -ForegroundColor Green } catch { Write-Warning 'Server still not available — please start it manually and re-run the script.'; exit 1 }
    } else {
        Write-Host "Hint: re-run with -StartServer to attempt automatic start, or start the server manually (python app.py)." -ForegroundColor Yellow
        exit 1
    }
}

# 2) Start or configure ngrok
$ngrokExe = Join-Path (Get-Location) 'ngrok\ngrok.exe'
$ngrokProcess = $null
if (-not (Test-Path $ngrokExe)) {
    Write-Warning "No local ngrok binary found at: $ngrokExe. Please download ngrok and place it in the 'ngrok' folder or install it system-wide."
} else {
    if ($NgrokAuthtoken) {
        & $ngrokExe authtoken $NgrokAuthtoken | Out-Null
        Write-Host 'Ngrok authtoken installed (not persisted to repo).' -ForegroundColor Green
    } else {
        Write-Host 'No NGROK_AUTHTOKEN provided — ngrok may refuse to create public tunnels.' -ForegroundColor Yellow
    }

    # Start ngrok in background
    Write-Host 'Starting ngrok http 5000...' -ForegroundColor Cyan
    $ngrokProcess = Start-Process -FilePath $ngrokExe -ArgumentList 'http','5000' -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 2

    # Wait for API to report a HTTPS tunnel
    $publicUrl = $null
    for ($i=0; $i -lt 20 -and -not $publicUrl; $i++) {
        Start-Sleep -Seconds 1
        try {
            $t = Invoke-RestMethod -Uri 'http://127.0.0.1:4040/api/tunnels' -ErrorAction Stop
            if ($t.tunnels.Count -gt 0) {
                # prefer https tunnel
                $https = $t.tunnels | Where-Object { $_.public_url -like 'https:*' } | Select-Object -First 1
                if ($https) { $publicUrl = $https.public_url } else { $publicUrl = $t.tunnels[0].public_url }
            }
        } catch {}
    }
    if (-not $publicUrl) { Write-Warning 'ngrok did not report a public tunnel; check the ngrok window or your authtoken.' } else { Write-Host "ngrok public URL: $publicUrl" -ForegroundColor Green }
}

# 3) Register Telegram webhook
if (-not $TelegramToken) { Write-Warning 'No TELEGRAM_TOKEN provided — cannot register Telegram webhook.' } else {
    if (-not $publicUrl) { Write-Warning 'No public URL (ngrok) available; cannot register Telegram webhook until you have an HTTPS endpoint.' } else {
        $setUrl = "https://api.telegram.org/bot$TelegramToken/setWebhook"
        $body = @{ url = "$publicUrl/webhook/telegram" }
        try {
            $resp = Invoke-RestMethod -Uri $setUrl -Method Post -Body $body -ErrorAction Stop
            Write-Host "Telegram setWebhook response: $($resp | ConvertTo-Json -Depth 2)" -ForegroundColor Green
        } catch { Write-Error "Failed to set Telegram webhook: $($_.Exception.Message)" }

        # getWebhookInfo
        try {
            $info = Invoke-RestMethod -Uri "https://api.telegram.org/bot$TelegramToken/getWebhookInfo" -ErrorAction Stop
            Write-Host "getWebhookInfo: $($info | ConvertTo-Json -Depth 3)" -ForegroundColor Cyan
        } catch { Write-Warning 'Failed to fetch Telegram webhook info.' }
    }
}

# 4) Register Twilio webhook (best-effort)
if (-not ($TwilioSid -and $TwilioAuth)) {
    Write-Warning 'Twilio SID and/or Auth Token not provided — skipping Twilio webhook registration.'
} else {
    if (-not $publicUrl) { Write-Warning 'No public URL (ngrok) available; cannot register Twilio webhook until you have an HTTPS endpoint.' } else {
        # Attempt to find an IncomingPhoneNumber by the WhatsApp number
        $phone = $WhatsappNumber -replace '^whatsapp:', ''
        $queryUrl = "https://api.twilio.com/2010-04-01/Accounts/$TwilioSid/IncomingPhoneNumbers.json?PhoneNumber=%2B$phone"
        try {
            $found = Invoke-RestMethod -Uri $queryUrl -Credential (New-Object System.Management.Automation.PSCredential($TwilioSid,(ConvertTo-SecureString $TwilioAuth -AsPlainText -Force))) -ErrorAction Stop
            if ($found -and $found.incoming_phone_numbers.Count -gt 0) {
                $sid = $found.incoming_phone_numbers[0].sid
                Write-Host "Found IncomingPhoneNumber sid: $sid" -ForegroundColor Green
                # Update webhook: use SmsUrl / SmsMethod to receive messages
                $updateUrl = "https://api.twilio.com/2010-04-01/Accounts/$TwilioSid/IncomingPhoneNumbers/$sid.json"
                $post = @{ SmsUrl = "$publicUrl/webhook/whatsapp"; SmsMethod = 'POST' }
                $resp = Invoke-RestMethod -Uri $updateUrl -Method Post -Credential (New-Object System.Management.Automation.PSCredential($TwilioSid,(ConvertTo-SecureString $TwilioAuth -AsPlainText -Force))) -Body $post -ErrorAction Stop
                Write-Host "Twilio IncomingPhoneNumbers update response sid: $($resp.sid)" -ForegroundColor Green
            } else {
                Write-Warning 'No IncomingPhoneNumber resource found for that phone number; you may need to configure the webhook via the Twilio Console or use Twilio Messaging Services. Attempting to send a test WhatsApp message instead.'
                # Try to send a test WhatsApp message (best-effort)
                $messagesUrl = "https://api.twilio.com/2010-04-01/Accounts/$TwilioSid/Messages.json"
                $from = $WhatsappNumber
                $to = $WhatsappNumber
                $body = 'Test message from register_webhooks.ps1 - please reply to verify webhook.'
                try {
                    $resp = Invoke-RestMethod -Uri $messagesUrl -Method Post -Credential (New-Object System.Management.Automation.PSCredential($TwilioSid,(ConvertTo-SecureString $TwilioAuth -AsPlainText -Force))) -Body @{ From = $from; To = $to; Body = $body } -ErrorAction Stop
                    Write-Host "Twilio send message response sid: $($resp.sid)" -ForegroundColor Green
                } catch {
                    Write-Warning "Failed to send Twilio test message: $($_.Exception.Message)"
                }
            }
        } catch {
            Write-Warning "Twilio API query failed: $($_.Exception.Message)" -ForegroundColor Yellow
            Write-Host 'Manual action: open Twilio Console -> Phone Numbers (or Messaging Services) -> configure the webhook URL to' "$publicUrl/webhook/whatsapp"
        }
    }
}

# 5) Verification tests (dry-run POST to local endpoints)
Write-Host 'Running dry-run webhook posts to local server to verify handlers...' -ForegroundColor Cyan
try {
    # Telegram dry-run
    $sample = @{ update_id = 123456; message = @{ message_id = 1; from = @{ id = 1111; username = 'test_user' }; chat = @{ id = 1111 }; date = [int][double]::Parse((Get-Date -UFormat %s)); text = 'hello test' } }
    $tResp = Invoke-RestMethod -Uri 'http://127.0.0.1:5000/webhook/telegram' -Method Post -Body ($sample | ConvertTo-Json -Depth 5) -ContentType 'application/json' -ErrorAction Stop
    Write-Host 'Telegram dry-run POST returned' -ForegroundColor Green
} catch { Write-Warning "Telegram dry-run failed: $($_.Exception.Message)" }

try {
    # Twilio dry-run: simulate form POST
    $form = @{ From = $WhatsappNumber; Body = 'hello whatsapp test' }
    $wResp = Invoke-RestMethod -Uri 'http://127.0.0.1:5000/webhook/whatsapp' -Method Post -Body $form -ContentType 'application/x-www-form-urlencoded' -ErrorAction Stop
    Write-Host 'WhatsApp (Twilio) dry-run POST returned' -ForegroundColor Green
} catch { Write-Warning "WhatsApp dry-run failed: $($_.Exception.Message)" }

# 6) Cleanup
Write-Host 'Cleaning up temporary processes & sensitive variables...' -ForegroundColor Cyan
if ($ngrokProcess -and -not $ngrokProcess.HasExited) {
    try { Stop-Process -Id $ngrokProcess.Id -Force; Write-Host 'Stopped ngrok process.' -ForegroundColor Green } catch { Write-Warning 'Failed to stop ngrok process; you may stop it manually.' }
}

# Unset sensitive env vars if they were passed as params (do not unset global environment unless user set)
if ($NgrokAuthtoken) { Remove-Item Env:NGROK_AUTHTOKEN -ErrorAction SilentlyContinue }
if ($TwilioSid) { Remove-Item Env:TWILIO_ACCOUNT_SID -ErrorAction SilentlyContinue }
if ($TwilioAuth) { Remove-Item Env:TWILIO_AUTH_TOKEN -ErrorAction SilentlyContinue }
Write-Host 'Done. Check logs and your app server for incoming messages from Telegram and WhatsApp to complete verification.' -ForegroundColor Green

# End of script
