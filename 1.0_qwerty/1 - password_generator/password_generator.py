import secrets
import string

def password_generator(length):
    characters = string.ascii_letters + string.digits + string.punctuation
    password = "".join(secrets.choice(characters)for i in range(length))
    return password

print("Hi! ")
hmp = int(input("How many passwords do you want to generate? : "))
hmc = int(input("How many characters do you want in your passwords? : "))

print("\nYour new passwords: ")
print("-" * 20)

with open("passwords.txt" , "w") as file: 
    for i in range(hmp): 
        new_password = password_generator(hmc)
        print(f"{i + 1}. {new_password}")
        file.write(f"{i + 1}. {new_password}\n")

print("-" * 20)