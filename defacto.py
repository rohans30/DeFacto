import os
import openai
import gradio as gr
import pdfplumber
from autogen import ConversableAgent

#######################################
# Configuration
#######################################
openai.api_key = os.getenv("OPENAI_API_KEY", None)

if openai.api_key is None:
    raise ValueError("No OpenAI API key found. Please set the OPENAI_API_KEY environment variable.")

llm_config = {"config_list": [{"model": "gpt-4o-mini", "api_key": os.environ.get("OPENAI_API_KEY")}]}

#######################################
# Utility: Extract text from PDF
#######################################
def extract_text_from_pdf(pdf_path: str) -> str:
    text_content = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_content.append(page_text)
    return "\n".join(text_content)

#######################################
# Prompts
#######################################
USER_ROLE_PROMPT = {
    "defense": "You are the defense attorney. Develop arguments to protect your client against the prosecution.",
    "prosecution": "You are the prosecuting attorney. Make a strong case against the defendant."
}

JUDGE_SYSTEM_PROMPT = """You are the judge presiding over a court case. Remain impartial, provide clarifications when asked, and explain legal reasoning. Your role is to maintain order and ensure a fair trial. You can ask questions and clarify points from both sides."""

WITNESS_SYSTEM_PROMPT = """You are a witness in this court case. Respond truthfully based on the given case facts. If you do not know the answer or it's not in the provided context, say so. Your knowledge is limited to the case context and general common sense."""

OPPOSING_COUNSEL_SYSTEM_PROMPT = """You are the opposing counsel. If the user has chosen to be the defense attorney, you are the prosecuting attorney, and vice versa. Challenge their statements, highlight weaknesses in their arguments, and provide counterpoints. Always remain professional."""

#######################################
# Agent Creation
#######################################
def create_agent(name: str, role_prompt: str, case_context: str):
    # Initialize a ConversableAgent with role-specific behavior
    system_message = f"{case_context}\n\n{role_prompt}"
    return ConversableAgent(
        name=name,
        llm_config=llm_config,
        system_message=system_message,
        # human_input_mode="NEVER"
    )

#######################################
# Gradio Handlers
#######################################
agents = {}
case_context = ""

def load_case_and_role(pdf_file, role):
    global agents, case_context

    if pdf_file is None:
        return [{"role": "system", "content": "Please upload a PDF file first."}]

    # Extract the text from the uploaded PDF
    case_context = extract_text_from_pdf(pdf_file.name)

    # Initialize agents
    agents["judge"] = create_agent("Judge", JUDGE_SYSTEM_PROMPT, case_context)
    agents["witness"] = create_agent("Witness", WITNESS_SYSTEM_PROMPT, case_context)
    agents["opposing"] = create_agent("Opposing Counsel", OPPOSING_COUNSEL_SYSTEM_PROMPT, case_context)

    # Store the user's role for context
    agents["user_role"] = USER_ROLE_PROMPT[role]

    # Return a welcome message in the chat
    return [{"role": "system", "content": f"Case loaded. You are the {role}. Begin your arguments."}]

def user_message_handler(user_message, chat_history):
    global agents

    if not agents:
        return chat_history + [{"role": "system", "content": "Please upload a case and select a role first."}]

    # Add user message to the conversation
    user_input = f"{agents['user_role']}\n\nUser says: {user_message}"
    chat_history.append({"role": "user", "content": user_message})

    # Judge responds
    judge_response = agents["judge"].generate_reply([{"role": "user", "content": user_input}])
    chat_history.append({"role": "assistant", "content": f"Judge: {judge_response}"})

    # Witness responds
    witness_response = agents["witness"].generate_reply([{"role": "user", "content": user_input}])
    chat_history.append({"role": "assistant", "content": f"Witness: {witness_response}"})

    # Opposing Counsel responds
    opposing_response = agents["opposing"].generate_reply([{"role": "user", "content": user_input}])
    chat_history.append({"role": "assistant", "content": f"Opposing Counsel: {opposing_response}"})

    return chat_history

#######################################
# Gradio Interface
#######################################
def build_interface():
    with gr.Blocks() as demo:
        gr.Markdown("# Courtroom Case Simulation")

        with gr.Row():
            pdf_input = gr.File(label="Upload Case PDF", file_types=[".pdf"])
            role_dropdown = gr.Dropdown(
                label="Choose Your Role",
                choices=["defense", "prosecution"],
                value="defense"
            )
        
        load_button = gr.Button("Load Case")
        chatbox = gr.Chatbot(label="Courtroom Chat", type="messages")
        user_input = gr.Textbox(label="Your Statement/Question")
        send_button = gr.Button("Send")

        # State to store chat history in Gradio
        state = gr.State([])  # empty list for chat history

        load_button.click(
            fn=load_case_and_role,
            inputs=[pdf_input, role_dropdown],
            outputs=chatbox
        )

        send_button.click(
            fn=user_message_handler,
            inputs=[user_input, chatbox],
            outputs=chatbox
        )

    return demo

if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
