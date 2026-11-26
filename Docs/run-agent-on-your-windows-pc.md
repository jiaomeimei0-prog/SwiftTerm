# Chay agent tren may Windows (My Machines)

Cai CLI thoi **chua du**. Agent chi dieu khien PC khi process worker dang chay.

## Bat worker (giu cua so mo)

```powershell
irm 'https://cursor.com/install?win32=true' | iex
agent login
cd $env:USERPROFILE\Documents\SwiftTerm
agent worker --computer-use --name windows-pc --worker-dir $PWD start
```

Roi mo https://cursor.com/agents -> chon **My Machines** -> **windows-pc** (hoac doi session hien tai thay worker online).

Kiem tra: agent goi list-self-hosted-workers phai thay worker `windows-pc`, khong con `workers: []`.

## Khac phuc Error 1033 (tunnel) tren PC

```powershell
cd $env:USERPROFILE\Documents\SwiftTerm
git checkout cursor/fix-named-tunnel-ps1-45fd
git pull
powershell -ExecutionPolicy Bypass -File .\scripts\windows-install-persistent-tunnel.ps1
```

Script nay chay origin + cloudflared **detached** (khong can giu cua so bring-up). Them `-AsService` neu PowerShell Admin de cai Windows Service.
