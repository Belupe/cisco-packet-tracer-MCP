# Servidor puente local (prototipo) para Packet Tracer 6.0.1 - version PowerShell.
# No necesita administrador ni instalar nada. Escucha SOLO en 127.0.0.1.
#
#   GET  /        panel (interface.html), lo abre el Script Module en un web view
#   GET  /next    siguiente codigo a ejecutar (204 si no hay)
#   POST /result  el panel devuelve el resultado (?id=N, cuerpo = texto)
#   POST /run     encola codigo JavaScript, responde el id (cuerpo = codigo)
#   GET  /get     ?id=N -> 200 + resultado, o 204 si aun no esta
#   GET  /ping    comprobacion
#
# Prototipo SIN token: antes de uso real hay que anadir autenticacion.
# Ejecutar:  powershell -ExecutionPolicy Bypass -File .\servidor.ps1

$Port = 54321
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Queue = New-Object System.Collections.Queue
$Results = @{}
$NextId = 1
$LastPoll = [DateTime]::MinValue

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://127.0.0.1:$Port/")
$listener.Start()
Write-Host "Puente en http://127.0.0.1:$Port  (Ctrl+C para parar)"

function Send($ctx, [int]$code, [string]$text, [string]$ctype = "text/plain; charset=utf-8") {
    $bytes = [Text.Encoding]::UTF8.GetBytes($text)
    $ctx.Response.StatusCode = $code
    $ctx.Response.ContentType = $ctype
    $ctx.Response.Headers.Add("Cache-Control", "no-store")
    if ($code -ne 204) {
        $ctx.Response.ContentLength64 = $bytes.Length
        $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
    }
    $ctx.Response.Close()
}

function Get-Query($ctx, [string]$name) {
    return $ctx.Request.QueryString[$name]
}

try {
    while ($listener.IsListening) {
        $task = $listener.GetContextAsync()
        while (-not $task.AsyncWaitHandle.WaitOne(500)) { }   # permite Ctrl+C
        $ctx = $task.GetAwaiter().GetResult()
        try {
            $req = $ctx.Request
            $hostHdr = $req.Headers["Host"]
            if ($hostHdr -ne "127.0.0.1:$Port") {
                Send $ctx 403 "host no permitido"; continue
            }
            $path = $req.Url.AbsolutePath
            $method = $req.HttpMethod

            if ($method -eq "GET" -and $path -eq "/") {
                $html = Get-Content -Raw -Encoding UTF8 (Join-Path $Here "interface.html")
                Send $ctx 200 $html "text/html; charset=utf-8"
            }
            elseif ($method -eq "GET" -and $path -eq "/ping") {
                $ago = if ($LastPoll -eq [DateTime]::MinValue) { -1 } else { [int]((Get-Date) - $LastPoll).TotalSeconds }
                Send $ctx 200 "ok last_poll_ago=$ago"
            }
            elseif ($method -eq "GET" -and $path -eq "/next") {
                $LastPoll = Get-Date
                if ($Queue.Count -gt 0) {
                    $item = $Queue.Dequeue()
                    Send $ctx 200 ("{0}`n{1}" -f $item.id, $item.code)
                } else { Send $ctx 204 "" }
            }
            elseif ($method -eq "GET" -and $path -eq "/get") {
                $id = [int](Get-Query $ctx "id")
                if ($Results.ContainsKey($id)) {
                    $r = $Results[$id]; $Results.Remove($id)
                    Send $ctx 200 $r
                } else { Send $ctx 204 "" }
            }
            elseif ($method -eq "POST" -and ($path -eq "/run" -or $path -eq "/result")) {
                if ($req.ContentLength64 -gt 1048576) { Send $ctx 413 "demasiado grande"; continue }
                $reader = New-Object IO.StreamReader($req.InputStream, [Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd()
                if ($path -eq "/run") {
                    $id = $NextId; $NextId++
                    $Queue.Enqueue(@{ id = $id; code = $body })
                    Send $ctx 200 "$id"
                } else {
                    $Results[[int](Get-Query $ctx "id")] = $body
                    Send $ctx 200 "ok"
                }
            }
            else { Send $ctx 404 "no encontrado" }
        } catch {
            try { Send $ctx 500 "$_" } catch { }
        }
    }
} finally {
    $listener.Stop()
}
