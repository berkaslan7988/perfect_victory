import hashlib 

def generate_hashes(text):
# Convert the string to bytes because hashing algorithms require byte-like objects
    text_bytes = text.encode("utf-8")
# Create an MD5 hash object and get the hexadecimal string representation
    md5_hash = hashlib.md5(text_bytes).hexdigest()
# Create a SHA256 hash object and get the hexadecimal string represantation    
    sha256_hash = hashlib.sha256(text_bytes).hexdigest()

    return md5_hash , sha256_hash
def save_to_file(text, md5_res, sha256_res):
    #"a" mode means 'append'. It creates the file if it doesn't exist, and adds new text to the end without deleting old content.

    with open ("hashes.txt", "a", encoding="utf-8") as file: 
         file.write(f"Original Text : {text}\n")
         file.write(f"MD5 Hash      : {md5_res}\n")
         file.write(f"SHA256 Hash   : {sha256_res}\n")
         file.write("-" * 50 + "\n")


print("=== Password Hash Generator ===")
print("Note: This tool demonstrates how passwords are mathematically scrambled.")

while True:
    #Get input from the user 
    user_input = input("\nEnter a text or password to hash (or type 'quit' to exit): ")

    if user_input.lower() == "quit" :
        print ("Bye!")
        break

    if not user_input:
        print("Error : Input cannot be empty. Please try again.")
        continue

    md5_result, sha256_result = generate_hashes(user_input)

    #Saving The Results
    
    save_to_file(user_input, md5_result, sha256_result)

    #Displaying The Results

    print("\n=== Hashing Results (Saved to hashes.txt) ===")
    print(f"Original Text : {user_input}")
    print(f"MD5 Hash      : {md5_result}")
    print(f"SHA256 Hash   : {sha256_result}")

    print("-" * 23)