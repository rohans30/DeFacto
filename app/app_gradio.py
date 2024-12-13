import os
import gradio as gr
from case_parser import parse_case_pdf
from prompts import (
    prosecuting_attorney_prompt, defense_attorney_prompt,
    judge_prompt, defendant_prompt, witness_prompt
)
from autogen import ConversableAgent, GroupChat, GroupChatManager
import time
import random
from openai import RateLimitError

# LLM Configuration
llm_config = {
    "config_list": [
        {"model": "gpt-4o-mini", "api_key": os.environ.get("OPENAI_API_KEY")}
    ],
    "temperature": 0.7,
}

def retry_with_exponential_backoff(func):
    def wrapper(*args, **kwargs):
        max_retries = 5
        retry_delay = 1
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except RateLimitError:
                if attempt == max_retries - 1:
                    raise
                retry_delay *= 2
                time.sleep(retry_delay + random.uniform(0, 1))
    return wrapper

def initialize_agents(user_role):
    agents = {}
    if user_role == "Defense Attorney":
        agents["prosecuting_attorney"] = ConversableAgent(
            "prosecuting_attorney",
            system_message=prosecuting_attorney_prompt,
            llm_config=llm_config,
            description="Acts as the Prosecuting Attorney in a mock trial..."
        )
        agents["human_proxy"] = ConversableAgent(
            "human_proxy-defense_attorney",
            llm_config=False,
            human_input_mode="NEVER",
            description="Acts as the Defense Attorney in a mock trial..."
        )
    else:
        agents["defense_attorney"] = ConversableAgent(
            "defense_attorney",
            system_message=defense_attorney_prompt,
            llm_config=llm_config,
            description="Acts as the Defense Attorney in a mock trial..."
        )
        agents["human_proxy"] = ConversableAgent(
            "human_proxy-prosecuting_attorney",
            llm_config=False,
            human_input_mode="NEVER",
            description="Acts as the Prosecuting Attorney in a mock trial..."
        )
    agents["judge_agent"] = ConversableAgent(
        "judge_agent",
        system_message=judge_prompt,
        llm_config=llm_config,
        description="Presides over the mock trial as the judge..."
    )
    agents["defendant_agent"] = ConversableAgent(
        "defendant_agent",
        system_message=defendant_prompt,
        llm_config=llm_config,
        description="Represents the defendant in the mock trial..."
    )
    agents["witness_agent"] = ConversableAgent(
        "witness_agent",
        system_message=witness_prompt,
        llm_config=llm_config,
        description="Represents witnesses in the mock trial..."
    )
    return agents

@retry_with_exponential_backoff
def start_simulation(user_role, case_text):
    agents = initialize_agents(user_role)
    group_chat = GroupChat(
        agents=agents.values(),
        messages=[],
        max_round=6,
        allow_repeat_speaker=False
    )

    group_chat_manager = GroupChatManager(
        groupchat=group_chat,
        llm_config=llm_config, 
        is_termination_msg=lambda x: "TERMINATE" in x.get("content", ""),
    )

    initial_message = f"""
I will be roleplaying as the {user_role} in this mock trial. I want to start from the direct examination where the defendant is already at the stand and I as the {user_role} am questioning them.

Here is the full trial document:

{case_text}
Is everyone ready?
"""
    # Initiate the chat
    agents["human_proxy"].initiate_chat(
        group_chat_manager,
        message=initial_message,
    )

    chat_history = [("System", initial_message)]
    return agents, group_chat, chat_history

@retry_with_exponential_backoff
def handle_user_message(user_message, agents, group_chat, chat_history):
    if not agents or not group_chat:
        return chat_history
    chat_history.append(("You", user_message))

    # Send user message to the group chat
    agents["human_proxy"].send({"content": user_message}, group_chat)

    # Retrieve all messages from the group_chat
    existing_msg_texts = {(m[0], m[1]) for m in chat_history}
    for m in group_chat.messages:
        formatted_msg = (m["sender"], m["content"])
        if formatted_msg not in existing_msg_texts:
            chat_history.append(formatted_msg)

    return chat_history

def parse_uploaded_file(f):
    if f is not None:
        return parse_case_pdf(f.name)
    return ""

def format_chat_history_for_chatbot(chat_history):
    # The Chatbot component expects a list of (user, assistant) message pairs.
    # We'll map:
    # - "You" as the user
    # - All other roles as assistant messages
    # This will produce a readable sequence in the UI even though multiple roles are involved.
    formatted = []
    current_user_message = None

    for role, content in chat_history:
        if role == "You":
            # This is a user message
            # If there's a pending user message without an assistant reply, finalize it first
            formatted.append((content, None))
        else:
            # Assistant (any role other than "You")
            # If the last message in formatted has None for assistant side, fill it
            if formatted and formatted[-1][1] is None:
                # Replace the last tuple's assistant response with this message
                formatted[-1] = (formatted[-1][0], f"{role}: {content}")
            else:
                # Start a new pair with empty user side
                formatted.append((None, f"{role}: {content}"))

    return formatted

def run_app():
    with gr.Blocks() as demo:
        gr.Markdown("# Law Case Study Simulation")

        user_role = gr.Dropdown(["Defense Attorney", "Prosecuting Attorney"], label="Choose Your Role")
        case_file = gr.File(label="Upload Case PDF")
        parsed_case = gr.Textbox(label="Parsed Case Text", lines=10)

        start_btn = gr.Button("Start Simulation")
        chatbox = gr.Chatbot(label="Chat History")
        user_input = gr.Textbox(label="Your Message")
        send_btn = gr.Button("Send")

        # States
        agents_state = gr.State({})
        groupchat_state = gr.State(None)
        chat_history_state = gr.State([])

        # Parse PDF file when uploaded
        case_file.change(fn=parse_uploaded_file, inputs=case_file, outputs=parsed_case)

        # Start simulation when button clicked
        def on_start_simulation(role, ctext):
            a, g, ch = start_simulation(role, ctext)
            formatted_ch = format_chat_history_for_chatbot(ch)
            return a, g, ch, formatted_ch

        start_btn.click(
            fn=on_start_simulation,
            inputs=[user_role, parsed_case],
            outputs=[agents_state, groupchat_state, chat_history_state, chatbox]
        )

        # Handle sending user message
        def on_send(msg, agents, groupchat, ch):
            ch = handle_user_message(msg, agents, groupchat, ch)
            formatted_ch = format_chat_history_for_chatbot(ch)
            return ch, formatted_ch

        send_btn.click(
            fn=on_send,
            inputs=[user_input, agents_state, groupchat_state, chat_history_state],
            outputs=[chat_history_state, chatbox]
        )

    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=7860)

if __name__ == "__main__":
    run_app()
