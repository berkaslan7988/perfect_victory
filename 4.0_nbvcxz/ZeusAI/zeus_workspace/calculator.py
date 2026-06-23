
def add(x, y):
    return x + y

def subtract(x, y):
    return x - y

def multiply(x, y):
    return x * y

def divide(x, y):
    if y == 0:
        return "Sıfıra bölme hatası!"
    return x / y

print("Basit Hesap Makinesi")
print("1. Toplama")
print("2. Çıkarma")
print("3. Çarpma")
print("4. Bölme")

while True:
    choice = input("İşlem seçin (1/2/3/4): ")

    if choice in ('1', '2', '3', '4'):
        try:
            num1 = float(input("İlk sayıyı girin: "))
            num2 = float(input("İkinci sayıyı girin: "))
        except ValueError:
            print("Geçersiz giriş. Lütfen sayı girin.")
            continue

        if choice == '1':
            print(num1, "+", num2, "=", add(num1, num2))
        elif choice == '2':
            print(num1, "-", num2, "=", subtract(num1, num2))
        elif choice == '3':
            print(num1, "*", num2, "=", multiply(num1, num2))
        elif choice == '4':
            print(num1, "/", num2, "=", divide(num1, num2))
        break
    else:
        print("Geçersiz giriş. Lütfen 1, 2, 3 veya 4 girin.")
