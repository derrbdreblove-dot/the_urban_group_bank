import json
from werkzeug.security import generate_password_hash

users = [
    {"username": "jdoe", "password": "password123", "fullname": "Johnathan Doe", "account_number": "483920174", "routing_number": "021000021", "balance": 7421000},
    {"username": "asimmons", "password": "mysecurepass", "fullname": "Alicia Simmons", "account_number": "602348291", "routing_number": "111000614", "balance": 5123400},
    {"username": "mcollins", "password": "collins2024", "fullname": "Michael Collins", "account_number": "208674553", "routing_number": "091000022", "balance": 2879000},
    {"username": "lchow", "password": "lydia88", "fullname": "Lydia Chow", "account_number": "758403219", "routing_number": "026009593", "balance": 6684000},
    {"username": "urbanholdings", "password": "urban123", "fullname": "Urban Holdings Ltd", "account_number": "304918273", "routing_number": "021000021", "balance": 7350000},
    {"username": "zenithcapital", "password": "zenith123", "fullname": "Zenith Capital Group", "account_number": "849302716", "routing_number": "111000614", "balance": 6210000},
    {"username": "apexinnovations", "password": "apex123", "fullname": "Apex Innovations LLC", "account_number": "507384920", "routing_number": "091000022", "balance": 4950000},
    {"username": "empiretrust", "password": "empire123", "fullname": "Empire Trust Partners", "account_number": "120948375", "routing_number": "026009593", "balance": 8120000},
    {"username": "novaindustries", "password": "nova123", "fullname": "Nova Industries Corp", "account_number": "730194826", "routing_number": "053000219", "balance": 5340000},
    {"username": "silverline", "password": "silver123", "fullname": "Silverline Global Investments", "account_number": "894203571", "routing_number": "121000358", "balance": 2590000}
]

for user in users:
    user["password"] = generate_password_hash(user["password"])

with open("data/users.json", "w") as f:
    json.dump(users, f, indent=2)

print("✅ users.json updated successfully with hashed passwords!")
