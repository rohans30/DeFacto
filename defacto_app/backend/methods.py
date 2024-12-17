import pdfplumber
from autogen import ConversableAgent, GroupChat, GroupChatManager
from constants import (
    prosecuting_attorney_prompt, defense_attorney_prompt,
    judge_prompt, defendant_prompt, witness_prompt, 
    judge_description, defendant_description, witness_description,
    human_proxy_prosecuting_attorney_description, human_proxy_defense_attorney_description,
    prosecuting_attorney_description, defense_attorney_description
)
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

def define_transitions(agents, user_role):
    disallowed_transitions = {
        agents["witness_agent"]: [agents["defendant_agent"], agents["witness_agent"]],
        agents["defendant_agent"]: [agents["witness_agent"], agents["defendant_agent"]],
        agents["judge_agent"]: [agents["judge_agent"]],
        agents["human_proxy"]: [agents["human_proxy"]],
    }

    if user_role == "DA":
        disallowed_transitions[agents["prosecuting_attorney"]] = [agents["prosecuting_attorney"], agents["human_proxy"]]
        disallowed_transitions[agents["human_proxy"]] = [agents["prosecuting_attorney"], agents["human_proxy"]]
    else:
        disallowed_transitions[agents["defense_attorney"]] = [agents["defense_attorney"], agents["human_proxy"]]
        disallowed_transitions[agents["human_proxy"]] = [agents["defense_attorney"], agents["human_proxy"]]
    
    return disallowed_transitions

# Utility to extract text from a PDF file
def extract_text_from_pdf(file):
    with pdfplumber.open(file) as pdf:
        text = "".join([page.extract_text() for page in pdf.pages])
    return text

#Utility to parse agent names
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
        elif content['name'] == "legal_analysis_agent":
            new_name = "Tutor Donny Defacto"
        elif content['name'] == "feedback_agent":
            new_name = "Tutor Donny Defacto"
        elif content['name'] == 'assistant':
            continue

        chat_history[i]['name'] = new_name
    return chat_history


def create_analysis_agents():
    agents = {}
    agents['legal_analysis_agent'] = ConversableAgent(
        name="legal_analysis_agent", 
        system_message=f"""
        You are LegalAnalysisAgent, an AI expert in analyzing legal court proceedings. This is the court proceeding you will be analyzing: {pdf_text} Your primary role is to explain the reasoning behind the behavior, questioning style, and responses of participants in a court transcript, including attorneys, judges, witnesses, and other legal professionals. You should provide insights into the legal strategies, arguments, and tactics used by the participants. You can also provide general legal knowledge and context to help the user understand the legal proceedings better. Your goal is to help the user gain a deeper understanding of the legal aspects of the court transcript. You can also answer questions related to legal concepts, procedures, and strategies. You have access to a wide range of legal knowledge and can provide detailed explanations on legal topics. You should provide accurate, informative, and insightful responses to the user's questions.
        """,
        llm_config=llm_config, 
    )

    agents['human_agent'] = ConversableAgent(
        "human_agent",
        llm_config=False,
        human_input_mode="ALWAYS",
        description="""
        Human user asking questions to the feedback agent.
        """
    )

    return agents