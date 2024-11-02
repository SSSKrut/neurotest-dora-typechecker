from pydantic import BaseModel
class User:
    def __init__(self, username, email):
        self.username = username
        self.email = email

    def display_user(self):
        print(f"Username: {self.username}, Email: {self.email}")