"""Module for generating search queries to support a research objective."""

from typing import List
import langchain.chat_models as chat_models
import langchain.output_parsers as output_parsers
from pydantic import BaseModel, Field
from langchain.prompts.chat import ChatPromptTemplate, HumanMessagePromptTemplate
try:
    from research_gpt.logging_config import logger
except ImportError:
    from logging_config import logger

# Define a Pydantic data model for the desired output structure
class QueryVariation(BaseModel):
    query: str = Field(
        description="A concise search query that helps to gather information about part of the objective. Target 4-6 words, never exceed 10 words."
    )
    relevancy_score: int = Field(
        description="An estimated score between 0 and 100, describing how relevant or important the search query is to the research objective."
    )


class QueryVariationList(BaseModel):
    output: List[QueryVariation]


# Create an instance of PydanticOutputParser using the defined data model
parser = output_parsers.PydanticOutputParser(pydantic_object=QueryVariationList)

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
    partial_variables={"format_instructions": parser.get_format_instructions()},
)

# Define ChatOpenAI model
chat_model = chat_models.ChatOpenAI(temperature=0.5, model_name="gpt-3.5-turbo")


def generate_search_queries(objective: str) -> List[QueryVariation]:
    """
    Generate search queries based on the given research objective.

    Args:
        objective (str): The research objective to generate search queries for.

    Returns:
        List[QueryVariation]: A list of search query variations.
    """
    logger.info("Generating search queries for objective: {}", objective)

    try:
        # Format the prompt
        _input = prompt.format_prompt(objective=objective)

        # Call the model
        response = chat_model(_input.to_messages())

        # Parse the response
        output = parser.parse(response.content)
        logger.info("Successfully generated search queries")

        return output.output

    except Exception as e:
        logger.error("Failed to generate search queries. Error: {}", e)
        raise e


# Test
if __name__ == "__main__":
    objective = (
        "Create a full fantasy rookie draft plan for the NFL for the 2023 Superflex Dynasty Fantasy Football League. "
        "Learn about all of the rookie players and the teams they were drafted to. "
        "Learn about the ceiling and floor of each player, potential risks or concerns, "
        "team-level impacts that may impact performance, and anything else that would impact draft selection decisions. "
        "The primary goal will be to develop rankings and tiers for each player to support the draft plan. "
        "Again, this is for a Superflex Dynasty league, which is often has much different player assessments than other styles of fantasy leagues."
    )
    try:
        search_queries = generate_search_queries(objective)
        print(search_queries)
    except Exception as e:
        logger.error("Error in main: {}", e)
