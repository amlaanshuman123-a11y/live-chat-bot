import os
import json
import time
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import openai

# ---------------- CONFIG ----------------
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

# Read credentials from Render environment variables
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
CLIENT_SECRET_JSON = os.environ.get("CLIENT_SECRET_JSON")
BROADCAST_ID = os.environ.get("BROADCAST_ID")          # Live stream ID
CHANNEL_NAME = os.environ.get("CHANNEL_NAME")          # Your YouTube channel name
# ----------------------------------------

# Write client_secret.json for Google OAuth
with open("client_secret.json", "w") as f:
    f.write(CLIENT_SECRET_JSON)

openai.api_key = OPENAI_API_KEY

# --------------- Functions ---------------
def authorize_youtube():
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)
    yt = build("youtube", "v3", credentials=creds)
    return yt

def get_live_chat_id(yt, broadcast_id):
    res = yt.liveBroadcasts().list(part="snippet", id=broadcast_id).execute()
    return res["items"][0]["snippet"]["liveChatId"]

def get_live_chat_messages(yt, live_chat_id, page_token=None):
    res = yt.liveChatMessages().list(
        liveChatId=live_chat_id,
        part="snippet,authorDetails",
        pageToken=page_token or "",
        maxResults=50
    ).execute()
    return res

def send_live_chat_message(yt, live_chat_id, text):
    body = {
        "snippet": {
            "liveChatId": live_chat_id,
            "type": "textMessageEvent",
            "textMessageDetails": {"messageText": text}
        }
    }
    yt.liveChatMessages().insert(part="snippet", body=body).execute()

def generate_reply(comment_text):
    prompt = f"Reply in a friendly, short sentence to this live comment: {comment_text}"
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}],
        max_tokens=50,
        temperature=0.7
    )
    return resp["choices"][0]["message"]["content"].strip()

# --------------- Main Bot ----------------
def main():
    yt = authorize_youtube()
    live_chat_id = get_live_chat_id(yt, BROADCAST_ID)
    next_page_token = None
    replied_comments = set()  # duplicate prevention

    while True:
        res = get_live_chat_messages(yt, live_chat_id, page_token=next_page_token)
        next_page_token = res.get("nextPageToken")
        messages = res.get("items", [])

        for msg in messages:
            text = msg["snippet"]["displayMessage"]
            author = msg["authorDetails"]["displayName"]
            msg_id = msg["id"]

            # Ignore self messages and duplicates
            if author != CHANNEL_NAME and msg_id not in replied_comments:
                reply = generate_reply(text)
                send_live_chat_message(yt, live_chat_id, reply)
                replied_comments.add(msg_id)
                print(f"{author}: {text} → Replied: {reply}")

        time.sleep(res.get("pollingIntervalMillis", 5000)/1000)

if __name__ == "__main__":
    main()
