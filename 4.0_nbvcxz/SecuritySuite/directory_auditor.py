import sys
import time
import requests

def brute_force_directories(target_url, wordlist):
    print(f"\n--- Starting Directory Bruteforce on: {target_url} ---", flush=True)
    print("Scanning for hidden directories and files...\n", flush=True)
    sys.stdout.flush()
    discovered_directories = []

    for word in wordlist:
        # Strip any accidental whitespace and build the full URL
        clean_word = word.strip()

        # FIXED: Removed the spaces around the forward slash to create valid URLs
        if not target_url.endswith("/"):
            full_url = f"{target_url}/{clean_word}"
        else:
            full_url = f"{target_url}{clean_word}"

        try:
            # Send an HTTP GET request to the generated URL
            # Allow_redirects=False captures the exact status code of the endpoint
            response = requests.get(full_url, allow_redirects=False, timeout=2.0)

            # HTTP Status Code 200 means the directory exists and is fully accessible
            if response.status_code == 200:
                print(f"[+] Found (200 OK) : {full_url}", flush=True)
                discovered_directories.append(full_url)
                sys.stdout.flush()

            # HTTP Status Code 301 or 302 means an active redirect route
            elif response.status_code in [301, 302]:
                print(f"[!] Redirect (301/302) : {full_url} -> Redirects elsewhere", flush=True)
                discovered_directories.append(full_url)
                sys.stdout.flush()

            # HTTP Status Code 403 means Forbidden (The directory exists but restriction is active)
            elif response.status_code == 403:
                print(f"[*] Restricted (403) : {full_url} (Directory exists but restricted)", flush=True)
                sys.stdout.flush()

        except requests.exceptions.RequestException:
            # Safely bypass connection drops, timeouts, or invalid routing targets
            pass
        
    print("\nScan Results", flush=True)
    if discovered_directories:
        # FIXED: Turned into an f-string so the count displays correctly
        print(f"Total discovered paths: {len(discovered_directories)}", flush=True) 
        for path in discovered_directories:
            print(f" - {path}", flush=True) 
            sys.stdout.flush()
    else:
        print("No hidden directories found from the provided wordlist.", flush=True)
        sys.stdout.flush()

# --- MAIN PROGRAM EXECUTION ---

print("--- Web Directory Bruteforcer Simulator ---", flush=True)
sys.stdout.flush()

# Example wordlist containing common hidden assets
sample_wordlist = [
    "admin", "login", "secret", "images", "backup", "db", "config.php", "test", "robots.txt", "uploads"
]

# Better Pipeline Management: 
# Instead of input(), we read the target URL directly passed as an argument by C#
if len(sys.argv) > 1:
    target = sys.argv[1]
else:
    # Safe fallback default for testing if run manually in terminal
    target = "http://localhost:8000"

time.sleep(1)
brute_force_directories(target, sample_wordlist)