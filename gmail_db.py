# gmail_db.py
import sqlite3
import json
from sqlite3 import Connection

from googleapiclient.discovery import Resource


def _setup_db(db_path='emails.db') -> Connection:
    """Create and initialize the SQLite database."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Create table for storing metadata
    c.execute(
        '''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, 
            thread_id TEXT,
            label_ids TEXT,
            snippet TEXT,
            history_id TEXT,
            internal_date INTEGER,
            size_estimate INTEGER
         )
         '''
    )

    # Create table for storing metadata (history ID tracking)
    c.execute(
        '''
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY, 
            value TEXT
        )
        '''
    )

    conn.commit()
    return conn


def _fetch_paginated_data(list_func, **kwargs):
    """Helper method for handling pagination."""
    response = list_func(**kwargs).execute()
    while response:
        yield response.get('messages', [])
        page_token = response.get('nextPageToken')
        if not page_token:
            break
        kwargs['pageToken'] = page_token
        response = list_func(**kwargs).execute()


class GmailDB(object):
    conn: Connection = None

    def __init__(self, service: Resource, user_id: str):
        # Get the authenticated user's email (user_id)
        user_profile = service.users().getProfile(userId='me').execute()
        user_id = user_profile['emailAddress']  # This is the user's email address

        # Use the user's email to create a database path
        db_path = f"{user_id}.db"

        self.conn = _setup_db(db_path=db_path)
        self.service = service
        self.user_id = user_id

    def __close__(self):
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

        # Insert or replace in the table, including message size estimate
        c.execute('''INSERT OR REPLACE INTO messages 
                     (id, thread_id, label_ids, snippet, history_id, internal_date, size_estimate)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (message_id, thread_id, label_ids, snippet, history_id, internal_date, size_estimate))
        self.conn.commit()

    def _fetch_and_store_messages(self, messages):
        """Helper function to fetch full metadata and store it."""
        for message_meta in messages:
            message = self.service.users().messages().get(userId=self.user_id, id=message_meta['id'],
                                                          format='metadata').execute()
            self._insert_message_metadata(message)

    def _sync_full_fetch(self):
        """Fetch all messages metadata when there is no historyId, with pagination."""
        print("Fetching all messages (no historyId found)...")
        try:
            for messages in _fetch_paginated_data(
                    self.service.users().messages().list, userId=self.user_id):
                self._fetch_and_store_messages(messages)
        except Exception as error:
            print(f"An error occurred while fetching messages: {error}")

    def _sync_with_history(self, history_id):
        """Sync messages using the Gmail History API, handling changes since the last historyId."""
        print(f"Syncing with Gmail history starting from historyId: {history_id}")
        try:
            for history_items in _fetch_paginated_data(
                    self.service.users().history().list, userId=self.user_id, startHistoryId=history_id):
                for record in history_items:
                    if 'messagesAdded' in record:
                        for added_message in record['messagesAdded']:
                            message_id = added_message['message']['id']
                            message = self.service.users().messages().get(
                                userId=self.user_id, id=message_id, format='metadata').execute()
                            self._insert_message_metadata(message)
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
            self._sync_with_history(history_id, )
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
        pass
