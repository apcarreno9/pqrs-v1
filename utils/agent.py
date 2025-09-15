import logging
from typing import Annotated
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

# Logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log")
    ]
)
logger = logging.getLogger(__name__)

class State(TypedDict):
    messages: Annotated[list, add_messages]

def make_agent_graph(
        llm: ChatOpenAI,
        tools: list,
        memory: InMemorySaver
) -> StateGraph: 

    builder = StateGraph(State)
    llm_with_tools = llm.bind_tools(tools)
    def chatbot(state: State):
        return {"messages": [llm_with_tools.invoke(state["messages"])]}
    builder.add_node("chatbot", chatbot)
    tool_node = ToolNode(tools=tools)
    builder.add_node("tools", tool_node)
    builder.add_conditional_edges("chatbot", tools_condition)
    builder.add_edge("tools", "chatbot")
    builder.add_edge(START, "chatbot")
    graph = builder.compile(checkpointer=memory)

    return graph