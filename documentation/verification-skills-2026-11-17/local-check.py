known = [0]
missing = ["poulet", "courgettes"]
subtotal = sum(known)
status = "partiel" if known and missing else "complet"
assert subtotal == 0 and status == "partiel"
print("T03-SEL-001 mini-check: 0 g, partiel; PASS")
