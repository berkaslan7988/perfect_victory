import random

def generate_random_mac() :

# hexadecimal characters used in MAC addresses (0-9 and A-F)

    hex_chars = "0123456789ABCDEF"

    mac_parts = []

# a mac address consists of 6 pairs of hexadecimal numbers 

    for i in range (6):

# select two random hexadecimal characters for one pair

        first_char = random.choice(hex_chars)
        second_char = random.choice(hex_chars)

# combine them into a pair (e.g., "A1")

        pair = first_char + second_char
        mac_parts.append(pair)

# join all 6 pairs with a colon ":" in between
# example : "1A:2B:3C:4D:5E:6F"

    generated_mac = ":".join(mac_parts)
    return generated_mac

# main program 

print("--- MAC Address Spoofer Simulator ---")
print("Generating valid, random and fake hardware identification addresses...")

while True:

    print("\n" + "=" * 40)
    choice = input("Press 'Enter' to generate a fake MAC address (or type 'quit' to exit) : ")
    
    if choice.lower() == 'quit':
        print("Exiting...")
        break
    

    fake_mac = generate_random_mac()
    print(f"\n[SUCCESS] New Fake MAC Address: {fake_mac}")
    print("This can be used to simulate network identity cloaking.")







 