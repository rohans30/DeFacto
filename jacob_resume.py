# %%
import pdfplumber
import autogen
from autogen import ConversableAgent
import os
from autogen import GroupChat
from autogen import GroupChatManager

# %%
def extract_text_from_pdf(file_path):
    with pdfplumber.open(file_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
    return text

# pdf_text = extract_text_from_pdf("mock_trial.pdf")
pdf_text = extract_text_from_pdf("./Mini-Mock-Trial-State-v.-Anderson-2016.pdf")


# %%
def estimate_tokens(text):
    return len(text) // 4

total_tokens = estimate_tokens(pdf_text)
print(f"Estimated tokens: {total_tokens}")


# %%
# openai_api_key = ""

# %%
# llm_config = {"config_list": [{"model": "gpt-4o-mini", "api_key": openai_api_key}]}
llm_config = {"config_list": [{"model": "llama3.2:3b", "api_type": "ollama", "client_host": "http://127.0.0.1:11434"}]}

# %%
# Ask the user to select a role
user_role = input("Would you like to role-play as the Defense Attorney or Prosecuting Attorney? Type DA or PA to confirm your selection.").strip().upper()

# Ensure valid selection
while user_role not in ["DA", "PA"]:
    user_role = input("Invalid role. Please enter DA or PA. \n\n Would you like to role-play as the Defense Attorney or Prosecuting Attorney? Type DA or PA to confirm your selection.").strip().upper()

agents = {}
human_proxy_role = ""

prosecuting_attorney_prompt = """
You are the Prosecuting Attorney (Deputy DA) in this mock trial. Your role is to present evidence and argue the case on behalf of the prosecution. Follow courtroom procedure, make legal arguments, and question witnesses to prove the defendant's guilt.
Do not simulate conversations with attorneys, the judge, or other witnesses. Focus on your role as the Prosecuting Attorney.
"""

defense_attorney_prompt = """
You are the Defense Attorney in this mock trial. Your role is to defend the defendant by creating reasonable doubt and presenting legal arguments that support their innocence. Cross-examine witnesses and challenge the prosecution's claims.
Do not simulate conversations with attorneys, the judge, or other witnesses. Focus on your role as the Defense Attorney.
"""

if user_role == "DA":
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

# %%
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

# %%
# human_proxy = ConversableAgent(
#     "human_proxy",
#     llm_config=False,  # no LLM used for human proxy
#     human_input_mode="ALWAYS",  # always ask for human input
#     description="Represents the human user roleplaying as the Deputy DA, directing the flow of the trial and interacting with other agents."
# )

# %%
group_chat = GroupChat(
    agents=agents.values(),
    messages=[],
    max_round=3,
    allow_repeat_speaker=False,
)

group_chat_manager = GroupChatManager(
    groupchat=group_chat,
    llm_config=llm_config, 
    is_termination_msg=lambda x: "TERMINATE" in x.get("content", ""),
)

# %%
initial_message = f"""
I will be roleplaying as the {human_proxy_role} in this mock trial. I want to start from the direct examination where the defendant is already at the stand and I as the {human_proxy_role} am questioning them.

Here is the full trial document:

{pdf_text}
Is everyone ready?
"""

# %%
#initial conversation
chat_result = agents["human_proxy"].initiate_chat(
    group_chat_manager,
    message=initial_message,
    summary_method="reflection_with_llm",
)



for i in range(5):
    
    last_agent, last_message = group_chat_manager.resume(messages = chat_result.chat_history, remove_termination_string="TERMINATE")

    next_user_input = input("EXAMPLE OF ASKING HUMAN INPUT TO STOP CHATS: How would you like to reply?")

    next_message = f"""
    I have been roleplaying as the {human_proxy_role} in this mock trial. My next question is {next_user_input}
    """

    chat_result = last_agent.initiate_chat(
        group_chat_manager,
        message = next_message,
        clear_history = False
    )

# %%
# from openai import OpenAI
# client = OpenAI()

# completion = client.chat.completions.create(
#     model="gpt-4o-mini",  # Choose model with sufficient token capacity
#     messages=[{"role": "system", "content": roleplay_prompt}]
# )

# print(completion.choices[0].message)



