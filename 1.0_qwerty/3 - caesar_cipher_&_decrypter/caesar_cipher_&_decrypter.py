def caesar_encrypt(plain_text, key):
    encrypted_text = ""

    for char in plain_text: 
       
        if char.isupper():
        
            #caesar cipher formula for uppercase letters
            #ascii value of 'A' is 65 (english alphabet has 26 letters)

            encrypted_char = chr((ord(char) + key - 65) % 26 + 65)
            encrypted_text += encrypted_char
        
        elif char.islower():

            #caesar cipher formula for lowercase letters
            #ascii value of 'a' is 97

            encrypted_char = chr((ord(char) + key - 97) % 26 + 97)
            encrypted_text += encrypted_char

        else: 
            encrypted_text += char

    return encrypted_text

def caesar_brute_force(cipher_text):
    print("\n--- Starting Brute Force Attack ---")
    print("trying all possible keys (0-25): ")


    for key in range(26): 
        decrypted_text = ""

        #reverse the shift
        for char in cipher_text:
            
            if char.isupper():

                 decrypted_char = chr((ord(char) - key - 65) % 26 + 65)
                 decrypted_text += decrypted_char
            
            elif char.islower():

                   decrypted_char = chr((ord(char) - key - 97) % 26 + 97)
                   decrypted_text += decrypted_char

            else:
                    decrypted_text += char

        print(f"key {key:02d}: {decrypted_text}")

#main program

print("--- Caesar Cipher & Decrypter Simulator ---")


#step 1 : encryption

message = input("enter a message to encrypt (english characters only): ")
shift_key = int(input("enter a shift key (a number between 1 and 25): "))

secret_message = caesar_encrypt(message, shift_key)
print(f"\nencrypted message: {secret_message} ")

#step 2 : brute force

input(f"\npress enter to start brute force attack simulation... ")
caesar_brute_force(secret_message)

















