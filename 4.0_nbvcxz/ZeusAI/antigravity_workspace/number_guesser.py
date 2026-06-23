import random

def number_guesser():
    secret_number = random.randint(1, 100)
    attempts = 0
    print("1 ile 100 arasında bir sayı tahmin et!")

    while True:
        try:
            guess = int(input("Tahminini gir: "))
            attempts += 1

            if guess < secret_number:
                print("Daha yüksek!")
            elif guess > secret_number:
                print("Daha düşük!")
            else:
                print(f"Tebrikler! Sayıyı {attempts} denemede buldun.")
                break
        except ValueError:
            print("Geçersiz giriş. Lütfen bir sayı girin.")

if __name__ == "__main__":
    number_guesser()
