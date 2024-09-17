import auth
from gmail_db import GmailDB

def main():
    with GmailDB() as gmailDB:
        gmailDB.fetch_messages()

        messages_by_sender: dict = gmailDB.get_messages_by_sender()


        # Sort senders by total size in descending order
        top_senders_by_size = sorted(messages_by_sender.items(), key=lambda item: item[1]['total_size'], reverse=True)[:10]

        # Sort senders by message count in descending order
        top_senders_by_count = sorted(messages_by_sender.items(), key=lambda item: item[1]['message_count'], reverse=True)[:10]

        print("\nTop 10 Senders by Total Message Size:")
        for idx, (sender, data) in enumerate(top_senders_by_size, start=1):
            print(f"{idx}. {sender} - Total Size: {data['total_size']} bytes, Number of Messages: {data['message_count']}")

        print("\nTop 10 Senders by Message Count:")
        for idx, (sender, data) in enumerate(top_senders_by_count, start=1):
            print(f"{idx}. {sender} - Number of Messages: {data['message_count']}, Total Size: {data['total_size']} bytes")



if __name__ == '__main__':
    main()