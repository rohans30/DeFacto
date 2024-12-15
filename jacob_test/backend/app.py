from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from autogen import ConversableAgent, GroupChat, GroupChatManager
import os
import uuid
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from methods import create_agents, extract_text_from_pdf, parse_agent_names, create_analysis_agents

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


class ContinueConversationRequest(BaseModel):
    session_id: str
    user_message: str

@app.post("/simulation/initailize")
async def initialize_conversation(pdf: UploadFile = File(...), role: str = Form(...)):
    if role not in ["DA", "PA"]:
        return JSONResponse(content={"error": "Invalid role. Use 'DA' or 'PA'."}, status_code=400)

    # Extract text from the uploaded PDF
    pdf_text = extract_text_from_pdf(pdf.file)

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return JSONResponse(content={"error": "OpenAI API key not configured."}, status_code=500)

    llm_config = {"config_list": [{"model": "gpt-4o-mini", "api_key": api_key}]}

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
    I will be roleplaying as the {role} in this mock trial. We will begin with the direct examination, where the defendant is already on the stand, and I, as the {role}, will be starting the questioning. However, this simulation will cover the entire court proceeding, including cross-examinations, objections, and any other trial phases.

    The prosecuting attorney should only speak after the judge has directly given them the floor, and the defense attorney should only speak after the prosecuting attorney has finished their questioning. The witnesses should only speak when directly addressed by the attorneys.

    When an attorney says they are finished with questioning, the next speaker should always be the judge. The judge will then decide who has the floor next based on the courtroom procedure.

    For context, the following document contains all the necessary details about the case, including background information, procedural context, and evidence:

    <context> {pdf_text} </context>

    Please ensure that all responses are appropriate for a courtroom setting, align with the role you are assigned, and adhere to the rules of courtroom procedure.
    """

    chat_result = agents["human_proxy"].initiate_chat(
        group_chat_manager,
        message=initial_message,
        summary_method="reflection_with_llm",
    )

    parsed_history = parse_agent_names(chat_result.chat_history[1:])

    return {"session_id": session_id, "response": parsed_history}

@app.post("/simulation/continue")
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


##### NEWWWWW

@app.post("/analysis/initialize")
async def initialize_analysis(pdf: UploadFile = File(...)):

    # Extract text from the uploaded PDF
    pdf_text = extract_text_from_pdf(pdf.file)

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return JSONResponse(content={"error": "OpenAI API key not configured."}, status_code=500)

    llm_config = {"config_list": [{"model": "gpt-4o-mini", "api_key": api_key}]}

    analysis_agent = ConversableAgent(
        name="legal_analysis_agent", 
        system_message=f"""
        You are LegalAnalysisAgent, an AI expert in analyzing legal court proceedings. This is the court proceeding you will be analyzing: {pdf_text} Your primary role is to explain the reasoning behind the behavior, questioning style, and responses of participants in a court transcript, including attorneys, judges, witnesses, and other legal professionals. You should provide insights into the legal strategies, arguments, and tactics used by the participants. You can also provide general legal knowledge and context to help the user understand the legal proceedings better. Your goal is to help the user gain a deeper understanding of the legal aspects of the court transcript. You can also answer questions related to legal concepts, procedures, and strategies. You have access to a wide range of legal knowledge and can provide detailed explanations on legal topics. You should provide accurate, informative, and insightful responses to the user's questions.
        """,
        llm_config=llm_config, 
    )

    human_agent = ConversableAgent(
        "human_agent",
        llm_config=False,
        human_input_mode="NEVER",
        code_execution_config=False,
        is_termination_msg=lambda message: True,
        description="""
        Human user asking questions to the feedback agent.
        """
    )

    chat_result = human_agent.initiate_chat(
        recipient=analysis_agent,
        message="First, can you summarize the court proceedings and the main legal issues discussed in the transcript?"
    )

    # Initialize session
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "human_agent": human_agent,
        "analysis_agent": analysis_agent,
    }
    print(chat_result)

    return {"session_id": session_id, "response": parse_agent_names(chat_result.chat_history)[1:]}

@app.post("/analysis/continue")
async def continue_conversation(request: ContinueConversationRequest):
    session = sessions.get(request.session_id)
    if not session:
        return JSONResponse(content={"error": "Session not found."}, status_code=404)

    analysis_agent = session['analysis_agent']
    human_agent = session['human_agent']
    
    chat_result = human_agent.initiate_chat(
        recipient=analysis_agent,
        message = request.user_message
    )

    # parse response for most recent message
    # index_of_next_message = 0
    # for i in range(len(chat_result.chat_history) - 1, -1, -1):
    #     response = chat_result.chat_history[i]
    #     if response['role'] == 'assistant':
    #         index_of_next_message = i + 1
    #         break
    return {"response": chat_result.chat_history[1:]}
