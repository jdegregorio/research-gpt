from langchain import LLMChain, PromptTemplate
from langchain.llms import OpenAI
from langchain.chat_models import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List


from langchain.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
)

# Define a Pydantic data model for your desired output structure
class QueryResult(BaseModel):
    query: str = Field(description="A concise search query that helps to gather information about part of the objective. Target 4-6 words, never exceed 10 words.")
    relevancy_score: int = Field(description="An estimated score between 0 and 100, describing how relevant or important the search query is to the research objective.")

class OutputList(BaseModel):
    output: List[QueryResult]

# Create an instance of PydanticOutputParser using the defined data model
parser = PydanticOutputParser(pydantic_object=OutputList)

# Create a PromptTemplate
prompt_template = """
You are a highly experienced professional researcher. You are skilled at using
Google Search to explore research topics and fully discover new areas. You are
proficient at starting with a root concept and expanding to adjacent search
topics that help support your primary research objective. You are excellent at
crafting google search queries that find the needed information.
---
INTERNAL PROCESS (NOT PART OF OUTPUT):
- Consider the most important aspects of the objective
- Consider tangential topics that are support of the objective
- Generate 10 queries that will retrieve all of the relevant content
---
OBJECTIVE:
{objective}
---
OUTPUT FORMAT INSTRUCTIONS:
{format_instructions}
"""

prompt = ChatPromptTemplate(
    messages=[
        HumanMessagePromptTemplate.from_template(prompt_template)
    ],
    input_variables=["objective"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

# Define ChatOpenAI model
chat_model = ChatOpenAI(temperature=0.5)

# Test
objective = "Create a full fantasy rookie draft plan for the NFL for the 2023 Superflex Dynasty Fantasy Football League. Learn about all of the rookie players and the teams they were drafted to. Learn about the ceiling and floor of each player, potential risks or concerns, team-level impacts that may impact performance, and anything else that would impact draft selection decisions. The primary goal will be to develop rankings and tiers for each player to support the draft plan. Again, this is for a Superflex Dynasty league, which is often has much different player assessments than other styles of fantasy leagues."
_input = prompt.format_prompt(objective=objective)
response = chat_model(_input.to_messages())
response
output = parser.parse(response.content)
output.output
