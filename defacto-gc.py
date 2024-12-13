import pdfplumber
import gradio as gr
import os
from autogen import ConversableAgent, GroupChat, GroupChatManager

# Function to extract text from PDF
def extract_text_from_pdf(file):
    with pdfplumber.open(file.name) as pdf:
        text = "".join(page.extract_text() for page in pdf.pages)
    return text

# Global variables to store agents and group chat manager
agents = {}
group_chat_manager = None
human_proxy_role = ""
initial_message = ""
chat_result = None

# Initialize agents based on user role and PDF content
def initialize_agents(pdf_text, user_role):
    global agents, group_chat_manager, human_proxy_role, initial_message, chat_result

    llm_config = {"config_list": [{"model": "gpt-4o-mini", "api_key": os.environ.get("OPENAI_API_KEY")}]}

    prosecuting_attorney_prompt = """
    You are the Prosecuting Attorney (Deputy DA) in this mock trial. Your role is to present evidence and argue the case on behalf of the prosecution. Follow courtroom procedure, make legal arguments, and question witnesses to prove the defendant's guilt.
    Do not simulate conversations with attorneys, the judge, or other witnesses. Focus on your role as the Prosecuting Attorney.
    """

    defense_attorney_prompt = """
    You are the Defense Attorney in this mock trial. Your role is to defend the defendant by creating reasonable doubt and presenting legal arguments that support their innocence. Cross-examine witnesses and challenge the prosecution's claims.
    Do not simulate conversations with attorneys, the judge, or other witnesses. Focus on your role as the Defense Attorney.
    """

    if user_role == "defense":
        human_proxy_role = "defense attorney"

        agents["prosecuting_attorney"] = ConversableAgent(
            "prosecuting_attorney",
            system_message=prosecuting_attorney_prompt,
            llm_config=llm_config,
            description="""
            Acts as the Prosecuting Attorney in a mock trial. 
            Responsible for representing the state or prosecution, presenting evidence, making legal arguments, and proving the defendant's guilt beyond a reasonable doubt.
            Tasks include delivering opening and closing statements, questioning witnesses, introducing exhibits, and arguing relevant points of law.
            """
        )

        agents["human_proxy"] = ConversableAgent(
            "human_proxy-defense_attorney",
            llm_config=False,
            human_input_mode="ALWAYS",
            description="""
            Acts as the Defense Attorney in a mock trial. 
            Responsible for representing the defendant by crafting a defense strategy, challenging the prosecution's case, cross-examining witnesses, and presenting evidence that supports the defendant's innocence or mitigates their liability.
            """
        )
    else:
        human_proxy_role = "defense attorney"
        
        agents["defense_attorney"] = ConversableAgent(
            "defense_attorney",
            system_message=defense_attorney_prompt,
            llm_config=llm_config,
            description="""
            Acts as the Defense Attorney in a mock trial. 
            Responsible for representing the defendant, delivering legal arguments, challenging the prosecution's claims, and advocating for the most favorable outcome for their client through legal defense strategies and courtroom procedure.
            """
        )

        agents["human_proxy"] = ConversableAgent(
            "human_proxy-prosecuting_attorney",
            llm_config=False,
            human_input_mode="ALWAYS",
            description="""
            Acts as the Prosecuting Attorney in a mock trial. 
            Responsible for presenting the case against the defendant, introducing evidence, questioning witnesses, and making legal arguments that establish the defendant's guilt under the applicable law.
            The Prosecuting Attorney seeks to achieve a conviction through clear and compelling arguments based on the trial's evidence.
            """
        )
    # Add judge and witness agents
    agents["judge_agent"] = ConversableAgent(
        "judge_agent", 
        system_message="""
        You are a judge presiding over a mock trial. 
        Answer all questions **only from the judge's perspective**, making legal rulings, managing courtroom procedures, and ensuring a fair trial. 
        Do not simulate conversations between other trial participants or generate responses for other roles. Focus solely on delivering rulings and courtroom instructions.
        """, 
        llm_config=llm_config,  
        description="""
        Presides over the mock trial as the judge. 
        Responsible for ensuring the trial proceeds fairly and in accordance with legal principles. 
        Duties include interpreting the law, making procedural rulings, managing courtroom conduct, 
        overseeing the admissibility of evidence, ruling on objections, and instructing the jury. 
        The judge must remain impartial while facilitating the smooth progression of the trial.
        """,
        is_termination_msg=lambda x: "TERMINATE" in x.get("content"),
    )

    agents["defendant_agent"] = ConversableAgent(
        name="defendant_agent", 
        system_message="""
        You are the defendant in a mock trial. 
        Answer all questions **only from the defendant's perspective**, responding truthfully and according to the trial document. 
        Do not simulate conversations with attorneys, the judge, or other witnesses. Wait until you are directly questioned or called to testify.
        """, 
        llm_config=llm_config, 
        description="""
        Represents the defendant in the mock trial. 
        Provides testimony when called to the stand, responds to direct and cross-examination questions, 
        and defends against accusations by presenting their version of events as established in the trial document. 
        The defendant must remain truthful and consistent with the provided case facts while adhering to courtroom protocol.
        """
    )

    agents["witness_agent"] = ConversableAgent(
        name="witness_agent", 
        system_message="""
        You are a witness in a mock trial. 
        Only respond **when a specific witness is referenced or called**. 
        Answer questions **only from the relevant witness’s perspective** based on the trial document. 
        Do not simulate conversations between the witness and other trial participants. Avoid generating content for other roles.
        """, 
        llm_config=llm_config, 
        description="""
        Represents all potential witnesses in the mock trial. 
        Responds only when directly referenced, adhering strictly to the details and character profiles described in the trial document.
        Follows legal procedures during direct and cross-examinations, providing truthful and consistent testimony in accordance with courtroom protocol.
        """
    )

    # Initialize group chat
    group_chat = GroupChat(
        agents=agents.values(),
        messages=[],
        max_round=2,
        allow_repeat_speaker=False,
    )

    group_chat_manager = GroupChatManager(
        groupchat=group_chat,
        llm_config=llm_config, 
        is_termination_msg=lambda x: "TERMINATE" in x.get("content", ""),
    )

    initial_message = f"""
    I will be roleplaying as the {human_proxy_role} in this mock trial. I want to start from the direct examination where the defendant is already at the stand and I as the {human_proxy_role} am questioning them.

    Here is the full trial document:

    {pdf_text}
    Is everyone ready?
    """

    chat_result = agents["human_proxy"].initiate_chat(
        group_chat_manager,
        message=initial_message,
        summary_method="reflection_with_llm",
    )

# Handle loading case and initializing agents
def load_case_and_role(pdf_file, role):
    pdf_text = extract_text_from_pdf(pdf_file)
    initialize_agents(pdf_text, role)
    return [("System", "Case loaded successfully. Agents initialized. You can start the chat.")]

# Handle user messages
def user_message_handler(user_message, chat_history):
    global group_chat_manager, chat_result

    chat_history = chat_history or []  # Ensure chat_history is initialized as a list

    if group_chat_manager:
        # Append the user's message to the chat history
        chat_history.append(("You", user_message))  # User messages on the right

        # Generate agent's response
        initial_message = user_message
        chat_result = agents["human_proxy"].initiate_chat(
            group_chat_manager,
            message=initial_message,
            summary_method="reflection_with_llm",
        )

        # Allow only relevant agents to reply once
        prev_chat = chat_result.chat_history
        last_agent, last_message = group_chat_manager.resume(
            messages=prev_chat, remove_termination_string="TERMINATE"
        )

        if last_message:
            chat_history.append((last_agent, last_message))  # Append the agent's meaningful response
    else:
        chat_history.append(("System", "Group chat manager is not initialized."))

    return chat_history

# Build Gradio interface
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
        chatbox = gr.Chatbot(label="Courtroom Chat")
        user_input = gr.Textbox(label="Your Statement/Question")
        send_button = gr.Button("Send")

        # State to store chat history
        state = gr.State([])

        load_button.click(
            fn=load_case_and_role,
            inputs=[pdf_input, role_dropdown],
            outputs=chatbox
        )

        send_button.click(
            fn=user_message_handler,
            inputs=[user_input, state],
            outputs=state  # Update state with the new chat history
        )

        send_button.click(
            fn=lambda state: state,  # Return updated chat history for display
            inputs=[state],
            outputs=chatbox
        )

    return demo

# Launch the app
if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
