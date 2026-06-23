import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import accuracy_score

def train_phishing_detector():
    print("--- AI Cyber Defense: Phishing Detection Engine ---")
    print("[*] Loading dataset and initializing AI model...")

    # 1. THE DATASET (Mini Simulation)
    # In a real scenario, you would use: data = pd.read_csv("emails.csv")
    # Labels: 1 = Phishing, 0 = Safe
    data = {
        "email_text": [
            "URGENT: Your bank account has been suspended. Click here.", 
            "Hey team, sending the presentation for tomorrow.", 
            "You won a $1000 gift card! Claim prize now.", 
            "Hi Mom, call me when you get off work.", 
            "Security Alert: Reset password immediately.", 
            "Let's grab lunch this Friday. New sushi place.", 
            "Netflix: Payment failed. Update billing details.", 
            "Invoice attached. Review payment details.", 
            "Your Apple ID is locked. Verify here.", 
            "Can we reschedule our meeting to 3 PM?",
            "Your Amazon package is delayed. Click link.",
            "Are we still on for dinner tonight?"
        ],
        "label": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0] # 6 Phishing, 6 Safe
    }

    df = pd.DataFrame(data)

    # 2. FEATURE EXTRACTION (Text to Numbers)
    # AI models only understand math. TF-IDF converts words into important mathematical values.
    vectorizer = TfidfVectorizer(stop_words='english')
    X = vectorizer.fit_transform(df['email_text']) # X: Mathematical representation of emails.
    Y = df['label'] # Y: The answers (1 or 0)

    # 3. SPLITTING DATA 
    # We split data to test the AI on emails it has never seen before

    X_train, X_test, Y_train, Y_test = train_test_split(X,Y, test_size=0.2, random_state=42)

    # 4. TRAINING THE AI MODEL
    # Naive Bayes is a classic and highly effective algorithm for text classification

    model = MultinomialNB()
    model.fit(X_train, Y_train) # This is where the actual "learning" happens

    # 5. EVALUATING THE MODEL

    predictions = model.predict(X_test)
    accuracy = accuracy_score(Y_test, predictions)
    print(f"[+] Model Training Complete! Initial Accuracy: {accuracy * 100:.1f}%\n")

    # 6. LIVE PREDICTION ENGINE

    print("--- Live Phishing Scanner ---")
    print("Type a sample email to see if the AI thinks it's a phishing attempt.")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("Scan Email > ")
        if user_input.lower() == 'quit':
            break
        if not user_input.strip():
            continue
        
        # We must vectorize the new input using the exact same mathematical rules
        user_input_vectorized = vectorizer.transform([user_input])

        # Make the prediction
        prediction = model.predict(user_input_vectorized)[0]

        # Calculate confidence / probability
        probabilities = model.predict_proba(user_input_vectorized)[0]
        confidence = probabilities[prediction] * 100

        if prediction == 1:
            print(f"[WARNING!] PHISHING DETECTED! (Confidence : {confidence:.1f}%)\n")
        else:
            print(f"[SAFE] Email appears legitimate. (Confidence : {confidence:.1f}%)\n")

if __name__ == "__main__":
    train_phishing_detector()










