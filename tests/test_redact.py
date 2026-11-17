"""Check contact-detail redaction. Run from the project folder: python -m tests.test_redact"""

from backend.resumes import redact

assert redact("jane.doe+cv@uni.edu.au") == "[email]"
assert redact("Call (555) 123-4567 or +1 555.123.4567") == "Call [phone] or [phone]"
assert redact("London +44 20 7946 0958") == "London [phone]"
assert redact("a@b.com (555) 123-4567 2019 - 2023") == "[email] [phone] 2019 - 2023"
for kept in ("Analyst, 2019 - 2023", "2015-2019 2019-2023", "2018 2019 2020", "GPA 3.8, 120 credits",
             "Grew revenue 25% to $1,200,000"):
    assert redact(kept) == kept, kept
print("redact ok")
