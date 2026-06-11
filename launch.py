import subprocess
import time
import sys
import os

def get_ngrok_url():
    """Get ngrok URL from API"""
    try:
        import requests
        response = requests.get("http://localhost:4040/api/tunnels", timeout=3)
        data = response.json()
        
        if 'tunnels' in data and len(data['tunnels']) > 0:
            for tunnel in data['tunnels']:
                if tunnel['public_url'].startswith('https'):
                    return tunnel['public_url']
            return data['tunnels'][0]['public_url']
    except:
        pass
    return None

def main():
    print("\n" + "="*70)
    print("🚀 INVENTORY SYSTEM LAUNCHER")
    print("="*70)
    
    # Kill existing ngrok
    print("\n[1/4] Cleaning up old processes...")
    subprocess.run(["taskkill", "/F", "/IM", "ngrok.exe"], 
                   stdout=subprocess.DEVNULL, 
                   stderr=subprocess.DEVNULL)
    time.sleep(2)
    
    # Start Flask
    print("[2/4] Starting Flask server...")
    flask_process = subprocess.Popen(
        [sys.executable, "app.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    print("[3/4] Waiting for Flask to initialize (5 seconds)...")
    time.sleep(5)
    
    # Start ngrok
    print("[4/4] Starting ngrok tunnel...")
    ngrok_process = subprocess.Popen(
        ["ngrok", "http", "5000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    print("      Waiting for ngrok to connect (10 seconds)...")
    time.sleep(10)
    
    # Try to get URL multiple times
    ngrok_url = None
    print("      Fetching public URL...")
    
    for attempt in range(10):
        ngrok_url = get_ngrok_url()
        if ngrok_url:
            break
        time.sleep(2)
        print(f"      Attempt {attempt + 1}/10...")
    
    print("\n" + "="*70)
    print("✅ SYSTEM READY!")
    print("="*70)
    
    if ngrok_url:
        print("\n" + "="*70)
        print("🌐 YOUR PUBLIC URL:")
        print("="*70)
        print(f"\n   {ngrok_url}")
        print("\n📤 COPY THIS URL AND SHARE IT!")
        print("   Access from any device, any network, anywhere!")
        print("\n   Note: First visit shows ngrok warning - click 'Visit Site'")
        print("="*70)
    else:
        print("\n⚠️  Could not fetch URL automatically")
        print("\n🔧 Manual steps:")
        print("   1. Open browser: http://localhost:4040")
        print("   2. Copy the 'Forwarding' https:// URL")
        print("   3. Share that URL")
    
    print("\n📱 Local access: http://localhost:5000")
    print("\n⚠️  KEEP THIS WINDOW OPEN!")
    print("   Press CTRL+C to stop all services")
    print("="*70 + "\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping services...")
        flask_process.terminate()
        ngrok_process.terminate()
        subprocess.run(["taskkill", "/F", "/IM", "ngrok.exe"], 
                       stdout=subprocess.DEVNULL, 
                       stderr=subprocess.DEVNULL)
        print("✅ Stopped!\n")

if __name__ == "__main__":
    main()
