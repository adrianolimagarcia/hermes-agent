import os
import signal
import sys
import tempfile
import threading
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from hermes.platform.webui.standalone import make_standalone_server

def main():
    port = int(os.environ.get("HAOS_PORT", 8788))
    host = os.environ.get("HAOS_HOST", "0.0.0.0")
    data_dir = os.environ.get("HAOS_DATA_DIR", "/tmp/haos_shared_data")
    
    print("=" * 70)
    print("🚀 STARTING HAOS STANDALONE CONTROL PLANE SERVER")
    print(f"[*] Bind Host: {host}")
    print(f"[*] Port:      {port}")
    print(f"[*] Data Dir:  {data_dir}")
    print("=" * 70)
    
    server, state, base_url = make_standalone_server(data_dir=data_dir, host=host, port=port)
    print(f"\n✅ Server running at: http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop.")

    def _shutdown_handler(signum, frame):
        print(f"\n[Signal {signum}] Stopping server cleanly...")
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)
    
    try:
        server.serve_forever()
    finally:
        server.server_close()
        print("Server socket closed cleanly.")

if __name__ == "__main__":
    main()
