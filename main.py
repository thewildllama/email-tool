import auth
from gmail_db import GmailDB


def display_senders_pagination(gmail_db: GmailDB):
    """Display senders in batches of 10, wait for user input, and process deletion."""
    senders_dict = gmail_db.get_messages_by_sender()
    sorted_senders = sorted(senders_dict.items(), key=lambda item: item[1]['total_size'], reverse=True)

    page_size = 10
    current_page = 0

    while True:
        # Paginate and show 10 senders at a time
        start_index = current_page * page_size
        end_index = start_index + page_size
        current_batch = sorted_senders[start_index:end_index]

        if not current_batch:
            print("No more senders to display.")
            break

        print("\nSenders sorted by total size (bytes):")
        for i, (sender_email, data) in enumerate(current_batch, start=1):
            print(f"{i}. {sender_email} - {data['total_size'] / 1048576:.2f} MB, {data['message_count']} messages")

        # Wait for user input
        choice = input("\nEnter the number of the sender to delete, 'n' for next page, 'f' for first page, or 'q' to quit: ").strip()

        if choice == 'q':
            print("Exiting.")
            break
        elif choice == 'n':
            current_page += 1
        elif choice == 'f':
            current_page = 0
        elif choice.isdigit():
            selected_index = int(choice) - 1
            if 0 <= selected_index < len(current_batch):
                selected_sender = current_batch[selected_index][0]
                confirm = input(f"Are you sure you want to delete all messages ({len(current_batch[selected_index][1]['messages'])}) from {selected_sender}? (y/n): ").strip().lower()
                if confirm == 'y':
                    gmail_db.delete_messages(current_batch[selected_index][1]['messages'])
                    # Refresh the list after deletion
                    senders_dict = gmail_db.get_messages_by_sender()
                    sorted_senders = sorted(senders_dict.items(), key=lambda item: item[1]['total_size'], reverse=True)
                    # current_page = 0  # Reset to the first page after deletion
                else:
                    print("Deletion cancelled.")
        else:
            print("Invalid input. Please try again.")

def main():
    with GmailDB() as gmailDB:
        gmailDB.fetch_messages()

        display_senders_pagination(gmailDB)


if __name__ == '__main__':
    main()