# Chay Cloud Agent truc tiep tren may Windows cua ban

Agent hien tai chay tren VM Linux (Cursor Cloud). **Khong** dieu khien duoc ban phim/chuot PowerShell tren PC Windows tru khi ban bat **self-hosted worker**.

## Bat worker (1 lan / moi session PC)

Tren Windows PowerShell:

```powershell
# Cai Cursor CLI neu chua co: xem https://cursor.com/docs/cloud-agent/self-hosted/my-machines
agent login
agent worker start
```

Giu cua so worker mo. Agent cloud se thay may ban trong `list-self-hosted-workers` va co the chay lenh **tren PC**.

## Khong co worker thi dung one-shot nay

```powershell
cd $env:USERPROFILE\Documents\SwiftTerm
git pull
powershell -ExecutionPolicy Bypass -File .\scripts\windows-bringup-toolvip1.ps1
```

Script tu:
- chon port bind duoc (tranh WinError 10013)
- ghi config tunnel `swiftterm-web` (khong dung toolvip1-ssh)
- mo HTTP + cloudflared (tranh Error 1033 khi dong cua so)
- in ket qua local/public

Van can ban xoa thu cong neu con:
- DNS **Worker** `patient-pond-3427` tren apex
- Access Application `toolvip1.top`
