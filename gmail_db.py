# gmail_db.py
import sqlite3
import json
import re
from sqlite3 import Connection
from time import perf_counter, sleep

import googleapiclient
from googleapiclient.errors import HttpError

import auth


def _setup_db(db_path='emails.db') -> Connection:
    """Create and initialize the SQLite database."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Create table for storing metadata
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, 
            thread_id TEXT,
            label_ids TEXT,
            sender TEXT,            
            sender_name TEXT,
            sender_email TEXT,
            sender_domain TEXT,
            snippet TEXT,
            history_id TEXT,
            internal_date INTEGER,
            size_estimate INTEGER
        )
    ''')

    # Create table for storing metadata (history ID tracking)
    c.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY, 
            value TEXT
        )
    ''')

    conn.commit()
    return conn


def _extract_sender(message) -> tuple:
    """Extract sender name, email, and domain from message headers."""
    headers = message.get('payload', {}).get('headers', [])
    sender_name, sender_email, sender_domain = 'Unknown', 'Unknown', 'Unknown'

    for header in headers:
        if header['name'] == 'From':
            sender = header['value']
            match = re.match(r'^(.*?)[\s]*<([^>]+)>$', sender)
            if match:
                sender_name = match.group(1).strip()
                sender_email = match.group(2).strip()
                sender_domain = sender_email.split('@')[-1] if '@' in sender_email else 'Unknown'
            else:
                # If the sender is just an email without a name
                sender_email = sender.strip('<>')
                sender_name = sender_email
                sender_domain = sender_email.split('@')[-1] if '@' in sender_email else 'Unknown'
            break

    return sender_name, sender_email, sender_domain


def _fetch_paginated_data(list_func, **kwargs):
    """Helper method for handling pagination."""
    response = list_func(**kwargs).execute()
    while response:
        yield response.get('messages', [])
        page_token = response.get('nextPageToken')
        if not page_token:
            break
        kwargs['pageToken'] = page_token
        try:
            response = list_func(**kwargs).execute()
        except HttpError as error:
            if error.resp.status == 429:
                print("Rate limit exceeded. Waiting for 1 seconds...")
                sleep(1)
                response = list_func(**kwargs).execute()
            elif error.resp.status == 403:
                print("Rate limit exceeded. Waiting for 10 seconds...")
                sleep(10)
                response = list_func(**kwargs).execute()


class GmailDB:
    conn: Connection = None

    def __init__(self):
        pass

    def __enter__(self):
        self.service = service = auth.authenticate_gmail("client_secret_196809605420-0jngb9rocnvqgeh0dv27ihq27s3ufi1a.apps.googleusercontent.com.json")

        user_profile = service.users().getProfile(userId='me').execute()
        self.user_id = user_profile['emailAddress']

        db_path = f"{self.user_id}.db"

        self.conn = _setup_db(db_path=db_path)

        # TODO: Add an option to bypass this.
        with self.conn.cursor() as c:
            # Query to select all message IDs
            c.execute("SELECT id FROM messages")

            # Fetch all message IDs and convert to a set
            self.already_saved_message_ids = {row[0] for row in c.fetchall()}

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

    def _set_history_id(self, history_id):
        """Store the current history ID for future tracking."""
        c = self.conn.cursor()
        c.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('historyId', ?)", (history_id,))
        self.conn.commit()

    def _get_history_id(self):
        """Retrieve the last stored history ID."""
        c = self.conn.cursor()
        c.execute("SELECT value FROM metadata WHERE key = 'historyId'")
        result = c.fetchone()
        return result[0] if result else None

    def _insert_message_metadata(self, message):
        """Insert or update message metadata in the database."""
        c = self.conn.cursor()

        # Extract necessary metadata fields
        message_id = message['id']
        thread_id = message['threadId']
        label_ids = json.dumps(message.get('labelIds', []))
        snippet = message.get('snippet', '')
        history_id = message.get('historyId', '')
        internal_date = message.get('internalDate', 0)
        size_estimate = message.get('sizeEstimate', 0)

        # Extract sender details
        sender_name, sender_email, sender_domain = _extract_sender(message)

        # Insert or replace in the table, including message size estimate and sender details
        c.execute('''
            INSERT OR REPLACE INTO messages 
            (id, thread_id, label_ids, sender, sender_name, sender_email, sender_domain, snippet, history_id, internal_date, size_estimate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (message_id, thread_id, label_ids, sender_email, sender_name, sender_email, sender_domain, snippet, history_id, internal_date, size_estimate))
        self.conn.commit()

    _messages_processed = 0

    def _batched_fetch_metadata_for_ids_and_store(self, message_ids) -> list[str]:
        """Fetch metadata for a batch of message IDs and store them."""

        messages = []
        unhandled_ids = []

        def callback(id, resp, ex):
            if ex:
                index = int(id) - 1
                print(f"An error occurred while fetching message request # {id}: {ex}")
                print(f"Adding {message_ids[index]} to retry list.")
                unhandled_ids.append(message_ids[index])
            else:
                messages.append(resp)

        batch = self.service.new_batch_http_request(callback=callback)

        for message_id in message_ids:
            if message_id in self.already_saved_message_ids:
                continue
            batch.add(
                self.service.users().messages().get(userId=self.user_id, id=message_id, format='metadata')
            )

        batch.execute()
        self._bulk_insert_message_metadata(messages)

        return unhandled_ids

    def _bulk_insert_message_metadata(self, messages):
        """Insert a batch of messages into the database in one transaction."""
        c = self.conn.cursor()
        insert_data = []

        for message in messages:
            message_id = message['id']
            thread_id = message['threadId']
            label_ids = json.dumps(message.get('labelIds', []))
            snippet = message.get('snippet', '')
            history_id = message.get('historyId', '')
            internal_date = message.get('internalDate', 0)
            size_estimate = message.get('sizeEstimate', 0)

            # Extract sender details
            sender_name, sender_email, sender_domain = _extract_sender(message)

            # Collect the data for bulk insert
            insert_data.append((
                message_id, thread_id, label_ids, sender_email, sender_name,
                sender_email, sender_domain, snippet, history_id, internal_date, size_estimate
            ))

        # Perform bulk insert
        with self.conn:
            c.executemany('''
                INSERT OR REPLACE INTO messages 
                (id, thread_id, label_ids, sender, sender_name, sender_email, sender_domain, snippet, history_id, internal_date, size_estimate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', insert_data)

        # TODO: Add a bypass option for this.
        for message in messages:
            self.already_saved_message_ids.add(message['id'])

    def _fetch_and_store_messages(self, messages):
        """Fetch multiple messages in batch using Gmail API's batch request and store them in the database."""
        batch_size = 25 # https://developers.google.com/gmail/api/guides/handle-errors#batch
        print(f"Processed {self._messages_processed} message metadata so far... Fetching {len(messages)} more messages...")
        self._messages_processed += len(messages)

        message_ids = [message_meta['id'] for message_meta in messages]

        retry_ids = []

        # Process messages in batches
        while len(message_ids) > 0:
            for i in range(0, len(message_ids), batch_size):
                batch_ids = message_ids[i:i + batch_size]
                retry_ids.extend(self._batched_fetch_metadata_for_ids_and_store(batch_ids))
            print(f"Retrying {len(retry_ids)} messages...")
            message_ids = retry_ids
            retry_ids = []
            sleep(1)


    def _sync_full_fetch(self):
        """Fetch all messages metadata when there is no historyId, with pagination."""
        print("Fetching all messages (no historyId found)...")

        for messages_page in _fetch_paginated_data(
                self.service.users().messages().list, userId=self.user_id, maxResults=500
        ):
            self._fetch_and_store_messages(messages_page)

    def _sync_with_history(self, history_id):
        """Sync messages using the Gmail History API, handling changes since the last historyId."""
        print(f"Syncing with Gmail history starting from historyId: {history_id}")
        try:
            for history_items in _fetch_paginated_data(
                    self.service.users().history().list, userId=self.user_id, startHistoryId=history_id):
                for record in history_items:
                    if 'messagesAdded' in record:
                        message_ids = [added_message['message']['id'] for added_message in record['messagesAdded']]
                        self._batched_fetch_metadata_for_ids_and_store(message_ids)
                    if 'messagesDeleted' in record:
                        for deleted_message in record['messagesDeleted']:
                            self._remove_message(deleted_message['message']['id'])
        except Exception as error:
            print(f"An error occurred while syncing with history: {error}")

    def _remove_message(self, msg_id):
        """Remove a message from the SQLite database."""
        c = self.conn.cursor()
        c.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
        self.conn.commit()

    def fetch_messages(self):
        """Fetch messages and synchronize metadata with SQLite DB."""
        # Get the stored history ID
        history_id = self._get_history_id()

        if history_id:
            # Sync using historyId if available
            self._sync_with_history(history_id)
        else:
            # If no historyId, perform a full fetch
            self._sync_full_fetch()

        # After syncing, update the historyId with the latest value
        try:
            profile = self.service.users().getProfile(userId=self.user_id).execute()
            self._set_history_id(profile['historyId'])
        except Exception as error:
            print(f"An error occurred while updating historyId: {error}")


    def get_messages_by_sender(self):
        """Return a dict of each sender mapped to:
           - the list of messages from that sender
           - the total size of the messages from that sender
           - the total number of messages from that sender
        """
        c = self.conn.cursor()
        query = '''
            SELECT sender, GROUP_CONCAT(id), SUM(size_estimate), COUNT(*)
            FROM messages
            GROUP BY sender
        '''
        c.execute(query)
        results = c.fetchall()

        senders_dict = {}
        for row in results:
            sender = row[0]
            message_ids = row[1].split(',') if row[1] else []
            total_size = row[2]
            message_count = row[3]

            senders_dict[sender] = {
                'messages': message_ids,
                'total_size': total_size,
                'message_count': message_count
            }

        return senders_dict
