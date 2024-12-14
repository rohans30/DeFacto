from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
import pdfplumber
from autogen import ConversableAgent, GroupChat, GroupChatManager
import os
import uuid
from pydantic import BaseModel
from constants import (
    prosecuting_attorney_prompt, defense_attorney_prompt,
    judge_prompt, defendant_prompt, witness_prompt, 
    judge_description, defendant_description, witness_description,
    human_proxy_prosecuting_attorney_description, human_proxy_defense_attorney_description,
    prosecuting_attorney_description, defense_attorney_description
)
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # This allows all origins, you can restrict this to your frontend domain for security.
    allow_credentials=True,
    allow_methods=["*"],  # This allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # This allows all headers
)


# To hold session data for simplicity (use a database for production!)
sessions = {}

# Utility to extract text from a PDF file
def extract_text_from_pdf(file):
    with pdfplumber.open(file) as pdf:
        text = "".join([page.extract_text() for page in pdf.pages])
    return text

def parse_agent_names(chat_history):
    for i,content in enumerate(chat_history):   
        new_name = None
        if content['name'] == "judge_agent":
            new_name = "Judge"
        elif content['name'] == "prosecuting_attorney":
            new_name = "Prosecuting Attorney"
        elif content['name'] == "defense_attorney":
            new_name = "Defense Attorney"
        elif content['name'] == "witness_agent":
            new_name = "Witness"
        elif content['name'] == "defendant_agent":
            new_name = "Defendant"
        elif content['name'] == 'assistant':
            continue

        chat_history[i]['name'] = new_name
    return chat_history

# Utility to create agents based on the role selected
def create_agents(user_role, pdf_text, llm_config):
    agents = {}

    if user_role == "DA":
        agents["prosecuting_attorney"] = ConversableAgent(
            "prosecuting_attorney",
            system_message = prosecuting_attorney_prompt,
            llm_config = llm_config,
            description = prosecuting_attorney_description
        )
        human_role = "defense_attorney"
        human_description = human_proxy_defense_attorney_description
    else:
        agents["defense_attorney"] = ConversableAgent(
            "defense_attorney",
            system_message=defense_attorney_prompt,
            llm_config=llm_config,
            description = defense_attorney_description
        )
        human_role = "prosecuting_attorney"
        human_description = human_proxy_prosecuting_attorney_description

    agents["human_proxy"] = ConversableAgent(
        f"human_proxy-{human_role}",
        human_input_mode="NEVER",
        code_execution_config=False,
        is_termination_msg=lambda message: True,
        description=human_description
    )

    agents["witness_agent"] = ConversableAgent(
        name="witness_agent", 
        system_message= witness_prompt, 
        llm_config=llm_config, 
        description = witness_description
    )

    agents["judge_agent"] = ConversableAgent(
        "judge_agent", 
        system_message = judge_prompt, 
        llm_config=llm_config,  
        description = judge_description,
    )

    agents["defendant_agent"] = ConversableAgent(
        name="defendant_agent", 
        system_message = defendant_prompt, 
        llm_config=llm_config, 
        description = defendant_description
    )

    return agents

class ContinueConversationRequest(BaseModel):
    session_id: str
    user_message: str

@app.post("/initialize")
async def initialize_conversation(pdf: UploadFile = File(...), role: str = Form(...)):
    if role not in ["DA", "PA"]:
        return JSONResponse(content={"error": "Invalid role. Use 'DA' or 'PA'."}, status_code=400)

    # Extract text from the uploaded PDF
    pdf_text = extract_text_from_pdf(pdf.file)

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return JSONResponse(content={"error": "OpenAI API key not configured."}, status_code=500)

    llm_config = {"config_list": [{"model": "gpt-4o", "api_key": api_key}]}

    # Create agents
    agents = create_agents(role, pdf_text, llm_config)

    group_chat = GroupChat(
        agents=agents.values(),
        messages=[],
        max_round=4,
        allow_repeat_speaker=False,
    )

    group_chat_manager = GroupChatManager(
        groupchat=group_chat,
        llm_config=llm_config,
        is_termination_msg=lambda x: "TERMINATE" in x.get("content", ""),
    )

    # Initialize session
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "group_chat_manager": group_chat_manager,
        "agents": agents,
    }

    initial_message = f"""
    I will be roleplaying as the {role} in this mock trial. We will begin with the direct examination, where the defendant is already on the stand, and I, as the {role}, 
    will conduct the questioning. However, this simulation will cover the entire court proceeding, including cross-examinations, objections, and any other trial phases.

    For context, the following document contains all the necessary details about the case, including background information, procedural context, and evidence:

    {pdf_text}

    Please ensure that all responses are appropriate for a courtroom setting, align with the role you are assigned, and adhere to the rules of courtroom procedure.
    """

    chat_result = agents["human_proxy"].initiate_chat(
        group_chat_manager,
        message=initial_message,
        summary_method="reflection_with_llm",
    )

    parsed_history = parse_agent_names(chat_result.chat_history[1:])

    return {"session_id": session_id, "response": parsed_history}

@app.post("/continue")
async def continue_conversation(request: ContinueConversationRequest):
    session = sessions.get(request.session_id)
    if not session:
        return JSONResponse(content={"error": "Session not found."}, status_code=404)

    group_chat_manager = session["group_chat_manager"]
    agents = session["agents"]

    chat_result = agents["human_proxy"].initiate_chat(
        group_chat_manager,
        message=request.user_message,
        clear_history=False,
    )

    # parse response for most recent message
    index_of_next_message = 0
    for i in range(len(chat_result.chat_history) - 1, -1, -1):
        response = chat_result.chat_history[i]
        if response['role'] == 'assistant':
            index_of_next_message = i + 1
            break
    
    parsed_history = parse_agent_names(chat_result.chat_history[index_of_next_message:])
    return {"response": parsed_history}
