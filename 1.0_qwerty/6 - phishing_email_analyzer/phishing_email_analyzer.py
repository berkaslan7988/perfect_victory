def analyze_email(email_text):

    # dictionary of suspicious words and their danger weights 

    suspicious_words = {

        "urgent": 4,
        "suspend": 5,
        "action required": 5,
        "click here": 5,
        "verify your account": 5,
        "password reset": 3,
        "free": 2,
        "winner": 3,
        "inherited": 4,
        "bank account": 3,
        "login immediately": 5

    }

    # convert email to lowercase so the search is case-insensitive

    email_lower = email_text.lower()

    risk_score = 0 
    detected_words = []

    # scan the email text for each suspicious word

    for word, weight in suspicious_words.items():
        if word in email_lower:

            # count how many times the word appears in the text 

            occurrences = email_lower.count(word)
            risk_score += weight * occurrences
            detected_words.append(f"'{word}' (Weight: {weight}, Found: {occurrences} time(s))")

    return risk_score, detected_words
        
# main program execution

print("--- Phishing Email Analyzer ---")
print("Paste an email content to analyze its security risk score")

while True:

    print("\n" + "=" * 40)
    user_email = input("Paste the email body text (or type 'quit' to exit):\n")

    if user_email.lower() == 'quit':
        print("Exiting Analyzer... Bye! ")
        break

    if not user_email.strip():

        print("Error: Email content cannot be empty.")
        continue

    # analyze the input text 
    score, triggers = analyze_email(user_email)


    # determine the threat level based on the risk score

    if score  == 0:

        threat_level = "SAFE (No known phishing triggers found.)"

    elif score <= 5:

        threat_level = "LOW RISK (Exercise normal caution..)"

    elif score <= 12:

        threat_level = "MEDIUM RISK (Suspicious content detected!.)"

    else:
        threat_level = "HIGH RISK (Very Likely to be a phishing attempt!!!)" 


# display the analysis results

    print("\n--- Analysis Report ---")
    print(f"Total Risk Score : {score}")
    print(f"Threat Level : {threat_level}")


    if triggers:
        print("\nDetected Triggers : ")
        for trigger in triggers :
            print (f"- {trigger}")

    else:
            print ("\nNo common trigger phishing keywords detected..")







