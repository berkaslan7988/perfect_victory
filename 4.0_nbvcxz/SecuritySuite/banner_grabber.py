import socket
import sys
import time

def grab_banner(target_host, target_port):
    print(f"\n--- Attempting Banner Grabbing on {target_host}:{target_port} ---", flush=True)

    try:
        # Create a socket object (IPv4, TCP)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Set a short timeout so we don't hang if the service doesn't send a banner
        s.settimeout(5.0)

        # Connect to the target host and port
        s.connect((target_host, target_port))

        # If it's an HTTP service, we must send a request header to trigger a response
        if target_port in [80, 8080]:
            # Send a standard HTTP HEAD request
            s.sendall(b"HEAD / HTTP/1.1\r\nHost: localhost\r\n\r\n")

        # Receive up to 1024 bytes of data from the target server
        # This now catches automatic banners (SSH, FTP) AND triggered HTTP banners
        banner = s.recv(1024)

        # Decode the byte response safely into a readable string
        decoded_banner = banner.decode('utf-8', errors='ignore').strip()

        if decoded_banner:
            print(f"[+] Service Banner Retrieved:\n\n{decoded_banner}\n", flush=True)
            print("[INFO] Vulnerability Scan: Search public CVE databases for this version.", flush=True)
        else:
            print("[-] Connected, but the service did not return a visible banner.", flush=True)

        s.close()

    except socket.timeout:
        print("[-] Connection Timeout: The service took too long to respond.", flush=True)
    except ConnectionRefusedError:
        print("[-] Connection Refused: The target port appears to be closed.", flush=True)
    except Exception as e:
        print(f"[-] An error occurred: {e}", flush=True)

# --- MAIN PROGRAM EXECUTION ---
print("--- Banner Grabbing (Service Version Detective) ---", flush=True)
sys.stdout.flush()

# Pipeline Management: Extract target IP and Port straight from C# arguments
if len(sys.argv) > 2:
    target_ip = sys.argv[1]
    try:
        target_port = int(sys.argv[2])
    except ValueError:
        target_port = 80
else:
    # Default fallbacks for manual terminal testing
    target_ip = "127.0.0.1"
    target_port = 80

time.sleep(1)
grab_banner(target_ip, target_port)