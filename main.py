import auth
from gmail_db import GmailDB

def main():
    # Authenticate and get Gmail API service
    service = auth.authenticate_gmail("client_secret_196809605420-0jngb9rocnvqgeh0dv27ihq27s3ufi1a.apps.googleusercontent.com.json")


    with GmailDB(service, 'me') as gmailDB:
        gmailDB.fetch_messages()

        messages_by_sender: dict = gmailDB.get_messages_by_sender()


if __name__ == '__main__':
    main()