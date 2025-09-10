import streamlit as st
from streamlit_chatbox import *
import time
import simplejson as json
import requests
import os

import os
import requests
import simplejson as json

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini" 

st.header("Jack's Team: Chat with your Data")

class OpenAILLM:
    def __init__(self, model: str = OPENAI_MODEL):
        self.model = model

    def _headers(self):
        if not OPENAI_API_KEY:
            return None, "Missing OPENAI_API_KEY (set it in Environment or st.secrets)."
        return {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }, None

    def chat(self, query: str):
        headers, err = self._headers()
        if err:
            return err, []

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": query}],
        }
        resp = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=60)
        try:
            data = resp.json()
        except Exception:
            return f"⚠️ Non-JSON response: {resp.text[:500]}", []

        if resp.status_code >= 400 or "error" in data:
            msg = data.get("error", {}).get("message", data)
            return f"API Error: {msg}", []

        if "choices" not in data:
            return f"Unexpected response: {data}", []

        text = data["choices"][0]["message"]["content"]
        return text, []

    def chat_stream(self, query: str):
        """Streaming chat generator (Server-Sent Events)."""
        headers, err = self._headers()
        if err:
         
            yield err, []
            return

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": query}],
            "stream": True,
        }
        with requests.post(OPENAI_URL, headers=headers, json=payload, stream=True) as r:
            text = ""
            for raw in r.iter_lines():
                if not raw:
                    continue
                try:
                    line = raw.decode("utf-8")
                    if line.startswith("data: "):
                        line = line[len("data: "):]
                    if line.strip() == "[DONE]":
                        break
                    data = json.loads(line)
                    delta = data["choices"][0]["delta"].get("content", "")
                    if delta:
                        text += delta
                        yield delta, []
                except Exception as e:
                    print("Stream error:", e)
   
llm = OpenAILLM()

chat_box = ChatBox(
    use_rich_markdown=True,
    user_theme="green",
    assistant_theme="blue",
)
chat_box.use_chat_name("chat1")  # add a chat conversation


def on_chat_change():
    chat_box.use_chat_name(st.session_state["chat_name"])
    chat_box.context_to_session()


with st.sidebar:
    st.subheader('start to chat using streamlit')
    chat_name = st.selectbox("Chat Session:", ["default", "chat1"], key="chat_name", on_change=on_chat_change)
    chat_box.use_chat_name(chat_name)
    streaming = st.checkbox('streaming', key="streaming")
    in_expander = st.checkbox('show messages in expander', key="in_expander")
    show_history = st.checkbox('show session state', key="show_history")
    chat_box.context_from_session(exclude=["chat_name"])

    st.divider()
    btns = st.container()

    file = st.file_uploader("chat history json", type=["json"])

    if st.button("Load Json") and file:
        data = json.load(file)
        chat_box.from_dict(data)


chat_box.init_session()
chat_box.output_messages()


def on_feedback(feedback, chat_history_id: str = "", history_index: int = -1):
    reason = feedback["text"]
    score_int = chat_box.set_feedback(feedback=feedback, history_index=history_index)
    st.session_state["need_rerun"] = True


feedback_kwargs = {
    "feedback_type": "thumbs",
    "optional_text_label": "welcome to feedback",
}

if query := st.chat_input('input your question here'):
    chat_box.user_say(query)
    if streaming:
        generator = llm.chat_stream(query)
        elements = chat_box.ai_say(
            [
                Markdown("thinking", in_expander=in_expander, expanded=True, title="answer"),
                Markdown("", in_expander=in_expander, title="references"),
            ]
        )
        time.sleep(1)
        text = ""
        for x, docs in generator:
            text += x
            chat_box.update_msg(text, element_index=0, streaming=True)
        chat_box.update_msg(text, element_index=0, streaming=False, state="complete")
        chat_box.update_msg("\n\n".join(docs), element_index=1, streaming=False, state="complete")
        chat_history_id = "some id"
        chat_box.show_feedback(
            **feedback_kwargs,
            key=chat_history_id,
            on_submit=on_feedback,
            kwargs={"chat_history_id": chat_history_id, "history_index": len(chat_box.history) - 1}
        )
    else:
        text, docs = llm.chat(query)
        chat_box.ai_say(
            [
                Markdown(text, in_expander=in_expander, expanded=True, title="answer"),
                Markdown("\n\n".join(docs), in_expander=in_expander, title="references"),
            ]
        )


cols = st.columns(2)
if cols[0].button('show me the multimedia'):
    chat_box.ai_say(Image(
        'https://tse4-mm.cn.bing.net/th/id/OIP-C.cy76ifbr2oQPMEs2H82D-QHaEv?w=284&h=181&c=7&r=0&o=5&dpr=1.5&pid=1.7'))
    time.sleep(0.5)
    chat_box.ai_say(Video('https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4'))
    time.sleep(0.5)
    chat_box.ai_say(Audio('https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4'))


btns.download_button(
    "Export Markdown",
    "".join(chat_box.export2md()),
    file_name=f"chat_history.md",
    mime="text/markdown",
)

btns.download_button(
    "Export Json",
    chat_box.to_json(),
    file_name="chat_history.json",
    mime="text/json",
)

if btns.button("clear history"):
    chat_box.init_session(clear=True)
    st.experimental_rerun()


if show_history:
    st.write(st.session_state)
