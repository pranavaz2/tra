
1. Python Backend Command
Run from the apps/api directory:

powershell
cd apps/api
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
API Base URL: http://localhost:8000
Swagger Docs: http://localhost:8000/docs
Health Check: http://localhost:8000/health
2. Expo Tunnel Command (Mobile App)
Run from the apps/mobile directory:

powershell
cd apps/mobile
npx expo start --tunnel
Tip for clearing cache if needed:

powershell
npx expo start --tunnel -c
3. Connecting Mobile to Backend via Tunnel (If using physical device / Expo Go)
If you are scanning the QR code on a physical phone using Expo Go, make sure your mobile .env has your reachable backend IP or tunnel URL:

In apps/mobile/.env:

env
EXPO_PUBLIC_API_URL=http://<YOUR_LOCAL_IP_OR_TUNNEL_URL>:8000
(Example: EXPO_PUBLIC_API_URL=http://192.168.1.5:8000)

1:26 PM
