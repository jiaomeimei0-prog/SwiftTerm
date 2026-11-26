# Chay agent tren may Windows (My Machines)

Cai ung dung / CLI **chua du**. Agent chi dieu khien PC khi process `agent worker start` dang chay (list-self-hosted-workers khong con `workers: []`).

## One-shot (khuyen dung)

Trong PowerShell tren PC:

```powershell
cd $env:USERPROFILE\Documents\SwiftTerm
git fetch origin
git checkout cursor/fix-named-tunnel-ps1-45fd
git pull
powershell -ExecutionPolicy Bypass -File .\scripts\windows-start-my-machine-and-tunnel.ps1
```

Script se:

1. Mo cua so **KEEP OPEN** chay `agent worker ... start` (ten `windows-pc`)
2. Cai origin + named tunnel `swiftterm-web` detached cho `toolvip1.top`

Neu chua co CLI:

```powershell
irm 'https://cursor.com/install?win32=true' | iex
agent login
```

Roi chay lai one-shot. Them `-AsService` (Admin) neu muon cloudflared Windows Service (origin van can user session / Scheduled Task sau reboot).

## Chi tunnel (khong worker)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows-install-persistent-tunnel.ps1
```

Chan doan: `.\scripts\diagnose-toolvip1.ps1` (doc port tu config, khong hard-code 8765).

## Khi nao agent "lam tren may ban" duoc

| Trang thai | Agent co the chay lenh tren PC? |
| --- | --- |
| Chi cai Use my computer / CLI | Khong |
| `agent worker start` dang chay, workers khong rong | Co |
| Dong cua so worker / sleep PC | Mat ket noi ngay |
