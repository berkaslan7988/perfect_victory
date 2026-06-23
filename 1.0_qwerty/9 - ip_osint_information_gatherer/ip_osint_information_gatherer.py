import requests

def get_ip_info(ip_address):

    # we use a free IP Geolocation API (ip-api.com) that doesn't require an API key

    url = f"http://ip-api.com/json/{ip_address}"

    try : 

        # send a GET request to the API

        response = requests.get(url)

        # parse the JSON response into a Python dictionary

        data = response.json()

        # check if the API successfully found the IP

        if data.get("status") == "success":

            print("\n--- Target IP Info ---")
            print(f"IP Address : {data.get('query')}")
            print(f"Country : {data.get('country')}")
            print(f"City : {data.get('city')}")
            print(f"ISP : {data.get('isp')}")
            print(f"Coordinates : {data.get('lat')}, {data.get('lon')}")
            print("--------------------------")

        else: 
            # triggered if the user enters an invalid IP address format
            
            print(f"\n[!] Error : Could not retrieve info for {ip_address}")
            print(f"Reason : {data.get('message')}")

    except requests.exceptions.RequestException as e :

        # catch connection errors

        print(f"\n[!] Connection Error : Could not reach the API. Check your internet connection.")

# main program execution

print("--- IP OSINT INFORMATION GATHERER ---")
print("Note : This tool uses public records to geolocate IP addresses. ")

while True:
    print("\n" + "=" * 40)
    target_ip = input("Enter a target IP address (or type 'quit' to exit): ")

    if target_ip.lower() == 'quit':
        print("Exiting...")
        break

    if not target_ip.strip():
        print("Error : IP adress cannot be empty")
        continue

    print(f"Scanning the globe for '{target_ip}'...")

    get_ip_info(target_ip)