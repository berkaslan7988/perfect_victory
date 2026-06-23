import requests

def brute_force_directories(target_url, wordlist):
    print(f"\n--- Starting Directory Bruteforce on : {target_url} ---")
    print("Scanning for hidden directories and files...\n")

    discovered_directories = []

    for word in wordlist:

        # strip any accidental whitespace and build the full URL
        clean_word = word.strip()

        # ensure the URL format is correct by joining target and directory

        if not target_url.endswith("/"):
            full_url = f"{target_url} / {clean_word}"

        else:
            full_url = f"{target_url}{clean_word}"

        try:
            # send a HTTP GET request to the generated URL
            # we set allow_redirects = False to see exact response of the directory

            response = requests.get(full_url , allow_redirects = False, timeout = 2.0)

            # HTTP Status Code 200 means the page / directory exists and accessible

            if response.status_code == 200:
                print(f"[+] Found (200 OK) : {full_url}")
                discovered_directories.append(full_url)

            # HTTP Status Code 301 or 302 means a redirect (often points to an existing directory)

            elif response.status_code in [301,302]:
                print(f"[!] Redirect (301/302) : {full_url} -> Redirects elsewhere")
                discovered_directories.append(full_url)


            # HTTP Status Code 403 means Forbidden (The directory exists but access is denied)


            elif response.status_code == 403:
                print(f"[*] Restricted (403) : {full_url} (Directory exists but restricted)")
            
        except requests.exceptions.RequestException:

             # skip errors like connection timeouts or invalid subdomains during brute force

             pass
        
    print("\nScan Results")
    if discovered_directories:
        print("Total discovered paths: {len(discovered_directories)}") 
        for path in discovered_directories:
            print(f" - {path}") 

    else:
        print("No hidden directories found from the provided wordlist.")


# main program execution

print("--- Web Directory Bruteforcer Simulator ---")

# example wordlist containing common hidden files and directories found on web servers

sample_wordlist = [

    "admin" , "login" , "secret" , "images" , "backup" , "db" , "config.php" , "test" , "robots.txt" , "uploads"

]

# we use a safe , legal and standart testing domain provided by the internet community
# do not scan real production websites without explicit legal authorization

target = "http://httpbin.org"

print(f"Target system configured as {target}")
print(f"Wordlist loaded with {len(sample_wordlist)} potential paths.")

input("\n Press 'Enter' to start directory discovery scan..")
brute_force_directories(target , sample_wordlist)

                
                