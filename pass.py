# Run this ONCE in a Python shell, then discard it
from werkzeug.security import generate_password_hash

print(generate_password_hash('mission_654321'))