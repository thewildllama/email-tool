# Email Cleanup Tool
Quick and dirty tool to enumerate an inbox, display the biggest space hogs, and clean up the mess.

Full disclosure, as a quick and dirty project, I definitely enlisted the help of ChatGPT extensively. I'm sure you'll
come across some of the telltale signs... But I did try to add sanity where I could. The "CLI" work is pretty much raw
ass GPT. But it works well, and that part is a total pain in the butt!

## Prerequisites
Assuming you are using the `wlc-email-tool` Google Cloud project, you can use the following steps to set up your local
environment.

### Dependencies
```bash
pip install --upgrade \
google-api-python-client \
google-auth-httplib2 \
google-auth-oauthlib
```

### OAuth consent screen test users
In the Google Developer Console, navigate to:
```
APIs & Services > OAuth consent screen
```

Towards the bottom of the page, you should see a "Test users" section. Add your email address to the list of test users.

### Client secrets
Download your client_secrets.json file from the Google Developer Console and save it in the root of the project as 
`client_secrets.json`.

In the Google Developer Console, navigate to:
```
APIs & Services > Credentials
```

Under the "OAuth 2.0 Client IDs" section, you should see a download icon (downward facing arrow with over a horizontal
line) to the right of each client ID. Click it and then click the "DOWNLOAD JSON" button on the popup.

## Running the tool
Simply execute the `main.py` script to run the tool. You will be prompted to authenticate with your Google account and
then the tool will enumerate your inbox. The Google API is quite restrictive in terms of rate limiting, so the tool is
rather slow when you first run. But subsequent runs will do incremental synchronization and be much faster.

Mailbox information is cached to `<user_id>.db`. If you want to force a full synchronization, simply delete this file,
or delete the `historyId` key from the `metadata` table.

When the client is synchronized, you will be presented with a list of the top 10 space hogs in your inbox and some
simple options to clean up the mess.

Type `1` to `10` to select a sender to delete. You will be presented with a confirmation dialogue. Press `y` to
permanently delete the messages or `n` to cancel.

The list will then present again.

To go to the next page of results, press `n`. To go to the first page, press `f`. To exit the tool, press `q`.

Have fun!

## Future work
I'm sure there's some big refactors that would help, but I think the biggest improvement might be from exploring the
IMAP API, or seeing if there is a better way to do synchronization.

I think we could also have some more flexibility in the presentation. Like showing results by domain tree. Or by sender
text. Or maybe even custom searches.

I'm sure we could do something about unsubscribing, too. I know there are some headers that can be used to unsubscribe,
but we could also just scrape some of the messages for unsubscribe links.

We don't do any work to show the messages, which might be helpful. I was fine with simply using the web interface to
explore the results further.



## Helpful links
 * [Python quickstart](https://developers.google.com/gmail/api/quickstart/python)
   * Also has good instructions for initial project setup!
 * [Information on rate limiting and other errors](https://developers.google.com/gmail/api/guides/handle-errors)
 * [Instructions for synchronizing IMAP](https://developers.google.com/gmail/api/guides/sync)
 * [REST API reference](https://developers.google.com/gmail/api/reference/rest)
   * [`users.messages.list`](https://developers.google.com/gmail/api/reference/rest/v1/users.messages/list)
   * [`users.history.list`](https://developers.google.com/gmail/api/reference/rest/v1/users.history/list)
   * [`users.messages.get`](https://developers.google.com/gmail/api/reference/rest/v1/users.messages/get)