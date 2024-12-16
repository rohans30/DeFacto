from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from autogen import ConversableAgent, GroupChat, GroupChatManager
import os
import uuid
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from methods import create_agents, extract_text_from_pdf, parse_agent_names, create_analysis_agents, define_transitions

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)


# To hold session data for simplicity
sessions = {}


class ContinueConversationRequest(BaseModel):
    session_id: str
    user_message: str

@app.post("/simulation/initialize")
async def initialize_conversation(pdf: UploadFile = File(...), role: str = Form(...)):
    if role not in ["DA", "PA"]:
        return JSONResponse(content={"error": "Invalid role. Use 'DA' or 'PA'."}, status_code=400)
    
    if role == "DA":
        human_proxy_role = "defense attorney"
    else:
        human_proxy_role = "prosecuting attorney"

    # Extract text from the uploaded PDF
    pdf_text = extract_text_from_pdf(pdf.file)

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return JSONResponse(content={"error": "OpenAI API key not configured."}, status_code=500)

    llm_config = {"config_list": [{"model": "gpt-4o-mini", "api_key": api_key}]}

    # Create agents
    agents = create_agents(role, pdf_text, llm_config)

    # Define transitions
    disallowed_transitions = define_transitions(agents, role)

    group_chat = GroupChat(
        agents=agents.values(),
        messages=[],
        allowed_or_disallowed_speaker_transitions=disallowed_transitions,
        speaker_transitions_type="disallowed",
        max_round=4,
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
    I will be roleplaying as the {human_proxy_role} in this mock trial. We will begin with the direct examination, where the defendant is already on the stand, and I, as the {human_proxy_role}, will be starting the questioning. However, this simulation will cover the entire court proceeding, including cross-examinations, objections, and any other trial phases.

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

    session = sessions[session_id]
    session["conversation_history"] = chat_result.chat_history
    session["user_role"] = human_proxy_role

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
    
    session["conversation_history"] = chat_result.chat_history


    # parse response for most recent message
    index_of_next_message = 0
    for i in range(len(chat_result.chat_history) - 1, -1, -1):
        response = chat_result.chat_history[i]
        if response['role'] == 'assistant':
            index_of_next_message = i + 1
            break
    
    parsed_history = parse_agent_names(chat_result.chat_history[index_of_next_message:])
    return {"response": parsed_history}


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
         You are LegalAnalysisAgent, an AI expert in analyzing legal court proceedings and legal notes and information. 
         This is the information you will be analyzing: <context> {pdf_text} </context> 
         Your primary role is to explain the legal information in the document and answer all of the user's questions to the best of your ability. 
         Your goal is to help the user gain a deeper understanding of the legal aspects of the court transcript. 
         You can also answer questions related to legal concepts, procedures, and strategies. 
         You have access to a wide range of legal knowledge and can provide detailed explanations on legal topics. 
         You should provide accurate, informative, and insightful responses to the user's questions. 
         Please don't respond in markdown, but respond in paragraph format and use newlines when necessary. Be as concise as possible with your answers.
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
        message="First, summarize the pdf that I uploaded."
    )

    # Initialize session
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "human_agent": human_agent,
        "analysis_agent": analysis_agent,
    }
    # print(chat_result)

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
    return {"response": parse_agent_names(chat_result.chat_history)[1:]}



### Feedback APIs

@app.post("/simulation/feedback")
async def handle_feedback(request: ContinueConversationRequest):
    session = sessions.get(request.session_id)
    if not session:
        return JSONResponse(content={"error": "Session not found."}, status_code=404)
    
    human_proxy_role = session["user_role"]

    # Check if feedback agents are already initialized
    if "feedback_agent" in session and "human_agent" in session:
        # Continue feedback logic
        feedback_agent = session['feedback_agent']
        human_agent = session['human_agent']
        group_chat_manager = session["group_chat_manager"]
        
        last_feedback_index = session.get('last_feedback_index', 0)
        conversation_history = session["conversation_history"]
        new_messages = conversation_history[last_feedback_index:]
        convo_string = group_chat_manager.messages_to_string(new_messages)

        chat_result = human_agent.initiate_chat(
            recipient=feedback_agent,
            message=f"{request.user_message} I am the {human_proxy_role}. Here are the new messages since the last feedback: {convo_string}",
            clear_history=False,
        )

        # Update feedback history
        # session['feedback_history'] = chat_result.chat_history

        # Find latest response index
        index_of_next_message = 0
        for i in range(len(chat_result.chat_history) - 1, -1, -1):
            response = chat_result.chat_history[i]
            if response['role'] == 'assistant':
                index_of_next_message = i + 1
                break

        return {"response": parse_agent_names(chat_result.chat_history[index_of_next_message:])}

    else:
        # Initialize feedback agents
        group_chat_manager = session["group_chat_manager"]
        conversation_history = session["conversation_history"]
        # print(f'conversation history {conversation_history}')
        convo_string = group_chat_manager.messages_to_string(conversation_history)
        # print(f'convo string {convo_string}')

        feedback_agent = ConversableAgent(
            name="feedback_agent", 
            system_message=f"""
            You are a legal feedback assistant for a mock trial simulation.
            Cite specific examples from the user's performance and provide constructive feedback on their courtroom performance, legal arguments, and trial strategy.
            Answer in paragraph format and be as concise as possible.
            """,
            llm_config=session["group_chat_manager"].llm_config,
        )

        human_agent = ConversableAgent(
            "human_agent",
            llm_config=False,
            human_input_mode="NEVER",
            is_termination_msg=lambda message: True,
        )

        feedback_result = human_agent.initiate_chat(
            recipient=feedback_agent,
            clear_history=False,
            message=f"""{request.user_message} I am the {human_proxy_role}. Here is the entire conversation history: {convo_string}""",
        )

        # Store feedback agents and history
        session['feedback_agent'] = feedback_agent
        session['human_agent'] = human_agent
        session['last_feedback_index'] = len(conversation_history)
        # session['feedback_history'] = feedback_result.chat_history

        parsed_feedback = parse_agent_names(feedback_result.chat_history[1:])
        return {"response": parsed_feedback}
