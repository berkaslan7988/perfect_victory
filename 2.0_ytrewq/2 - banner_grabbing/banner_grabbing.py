import socket 

def grab_banner(target_host, target_port):
    print(f"\n--- Attempting Banner Grabbing on {target_host}:{target_port} ---")

    try:

        # create a socket object (IPv4, TCP)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # set a short timeout so we don't hang if the service doesn't send a banner 
        s.settimeout(5.0)

        # connect the target host and port
        s.connect((target_host , target_port))

        # for some protocols (like HTTP/80), we need to send a basic request to
        # trigger the server to send its banner / header back

        if target_port == 80 or target_port == 8080:

            # send a standard HTTP HEAD request

            s.sendall(b"HEAD / HTTP/1.1\r\nHost: localhost \r\n\r\n ")

            # receive up to 1024 bytes of data from the target server

            banner = s.recv(1024)

            # decode the byte response into a readable string using 'errors = ignore' to prevent crashes from weird characters

            decoded_banner = banner.decode('utf-8', errors='ignore').strip()

            if decoded_banner:
                print(f"[+] Service Banner Retrieved: \n\n{decoded_banner}\n")
                print("[INFO] Vulnerability Scan: Search public CVE databases for this version.")

            else:
                print("[-] Connected, but the service did not return a visible banner")

            s.close()

    except socket.timeout:
        print("[-] Connection Timeout : The service took too long to respond.") 
    except ConnectionRefusedError:
        print("[-] Connection Refused : The target port appears to be closed.") 
    except Exception as e:
        print(f"[-] An error occurred: {e}")

# main program execution

print("--- Banner Grabbing (Service Version Detective) ---")

#target_ip = "telehack.com"
#target_port = 23

target_ip = (input("target ip : ")) 
target_port = int(input("target port : "))

print(f"Target host configured as : {target_ip}")
print(f"Target port configured as : {target_port}")

input("Press 'Enter' to start extracting the service banner...")
grab_banner(target_ip , target_port)