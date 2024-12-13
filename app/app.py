import streamlit as st
import pdfplumber
from DeFacto.app.constants import (
    prosecuting_attorney_prompt, defense_attorney_prompt,
    judge_prompt, defendant_prompt, witness_prompt, 
    judge_description, defendant_description, witness_description,
    human_proxy_prosecuting_attorney_description, human_proxy_defense_attorney_description,
    prosecuting_attorney_description, defense_attorney_description
)
from autogen import ConversableAgent
import os
from autogen import GroupChat
from autogen import GroupChatManager

# Function to extract text from PDF
def extract_text_from_pdf(file):
    with pdfplumber.open(file) as pdf:
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

# Function to safely extract response from ChatResult
def get_agent_response(chat_result):
    return chat_result.chat_history[-1]['content']

# Initialize session state for chat history
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# Initialize session state for agents and group chat
if 'agents_initialized' not in st.session_state:
    st.session_state.agents_initialized = False
    st.session_state.group_chat_manager = None
    st.session_state.agents = {}
    st.session_state.user_role = None
    st.session_state.human_proxy_role = ""
    st.session_state.pdf_text = ""

st.title("Law Case Simulation Chatbot")

# File uploader
uploaded_file = st.file_uploader("Upload Case PDF", type=["pdf"])

# Role selection
role = st.radio(
    "Select Your Role",
    ("Defense Attorney", "Prosecuting Attorney"),
    key="role_selection"
)

# Initialize Agents after file upload and role selection
if uploaded_file and role and not st.session_state.agents_initialized:
    with st.spinner("Initializing agents..."):
        # Extract text from the uploaded PDF
        st.session_state.pdf_text = extract_text_from_pdf(uploaded_file)

        # Set user role
        user_role = "DA" if role == "Defense Attorney" else "PA"
        st.session_state.user_role = user_role

        llm_config = {
            "config_list": [
                {"model": "gpt-4o-mini", "api_key": os.environ.get("OPENAI_API_KEY")}
            ],
            "temperature": 0.7,
        }

        agents = {}
        human_proxy_role = ""

        if user_role == "DA":
            human_proxy_role = "Defense Attorney"

            agents["prosecuting_attorney"] = ConversableAgent(
                "prosecuting_attorney",
                system_message=prosecuting_attorney_prompt,
                llm_config=llm_config,
                description=prosecuting_attorney_description
            )

            agents["human_proxy"] = ConversableAgent(
                "human_proxy-defense_attorney",
                llm_config=False,
                human_input_mode="NEVER",
                is_termination_msg=lambda message: True,
                description=human_proxy_defense_attorney_description
            )
        else:
            human_proxy_role = "Prosecuting Attorney"  # Corrected role

            agents["defense_attorney"] = ConversableAgent(
                "defense_attorney",
                system_message=defense_attorney_prompt,
                llm_config=llm_config,
                description=defense_attorney_description
            )

            agents["human_proxy"] = ConversableAgent(
                "human_proxy-prosecuting_attorney",
                llm_config=False,
                human_input_mode="NEVER",
                is_termination_msg=lambda message: True,
                description=human_proxy_prosecuting_attorney_description
            )

        agents["judge_agent"] = ConversableAgent(
            "judge_agent", 
            system_message=judge_prompt, 
            llm_config=llm_config,  
            description=judge_description,
            is_termination_msg=lambda x: "TERMINATE" in x.get("content", ""),
        )

        agents["defendant_agent"] = ConversableAgent(
            name="defendant_agent", 
            system_message=defendant_prompt, 
            llm_config=llm_config, 
            description=defendant_description
        )

        agents["witness_agent"] = ConversableAgent(
            name="witness_agent", 
            system_message=witness_prompt, 
            llm_config=llm_config, 
            description=witness_description
        )

        group_chat = GroupChat(
            agents=agents.values(),
            messages=[],
            max_round=6,
            allow_repeat_speaker=False,
        )

        group_chat_manager = GroupChatManager(
            groupchat=group_chat,
            llm_config=llm_config, 
            is_termination_msg=lambda x: "TERMINATE" in x.get("content", ""),
        )

        # Construct the initial message using f-string
        initial_message = f"""
        I will be roleplaying as the {human_proxy_role} in this mock trial. I want to start from the direct examination where the defendant is already at the stand and I as the {human_proxy_role} am questioning them.

        Here is the full trial document:

        {st.session_state.pdf_text}
        Is everyone ready?
        """

        # Initiate chat with the initial message
        chat_result = agents["human_proxy"].initiate_chat(
            group_chat_manager,
            message=initial_message,
            summary_method="reflection_with_llm",
        )

        # Extract the agent's response
        # agent_response = get_agent_response(chat_result)

        # # Append the initial message and agent's response to chat history
        # # st.session_state.chat_history.append(("System", initial_message))
        # st.session_state.chat_history.append(("LLM", agent_response))
        chats = chat_result.chat_history
        for c in chats:
            if c['content'] == initial_message: continue
            st.session_state.chat_history.append(("LLM", c['content']))

        # Update session state
        st.session_state.group_chat_manager = group_chat_manager
        st.session_state.agents = agents
        st.session_state.human_proxy_role = human_proxy_role  # Ensure this is set
        st.session_state.agents_initialized = True

# Chat interface
if st.session_state.agents_initialized:
    st.subheader("Chat History")
    chat_container = st.container()
    with chat_container:
        for speaker, message in st.session_state.chat_history:
            if speaker == "System":
                st.markdown(f"**{speaker}:** {message}")
            elif speaker == "LLM":
                st.markdown(f"**LLM:** {message}")
            else:
                st.markdown(f"**{speaker}:** {message}")

    st.subheader("Your Message")
    with st.form(key='chat_form', clear_on_submit=True):
        user_input = st.text_input("Type your message here:")
        submit_button = st.form_submit_button(label='Send')

    if submit_button and user_input:
        # Append user message to chat history
        st.session_state.chat_history.append((st.session_state.human_proxy_role, user_input))

        # Send the message to the agent
        chat_result = st.session_state.agents["human_proxy"].initiate_chat(
            st.session_state.group_chat_manager,
            message=user_input,
            clear_history=True,
        )

        # Extract the agent's response
        agent_response = get_agent_response(chat_result)

        # Append agent response to chat history
        st.session_state.chat_history.append(("LLM", agent_response))

    # Optionally, provide a button to reset the chat
    if st.button("Reset Chat"):
        st.session_state.chat_history = []
        st.session_state.agents_initialized = False
        st.experimental_rerun()

# Debugging: Display raw chat_result (optional)
if st.session_state.agents_initialized:
    st.subheader("Debug: Latest Chat Result")
    chat_result = st.session_state.agents["human_proxy"].initiate_chat(
        st.session_state.group_chat_manager,
        message="",  # Empty message to just get the last chat_result
        clear_history=False,
    )
    st.write(chat_result)

# Instructions if no file is uploaded
if not uploaded_file:
    st.info("Please upload a case PDF to start the simulation.")

# Instructions if role not selected
if uploaded_file and not st.session_state.agents_initialized:
    st.info("Please select your role to initialize the simulation.")
