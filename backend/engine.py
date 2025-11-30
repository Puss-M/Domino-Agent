import os
import json
import networkx as nx
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List, Literal

load_dotenv()

class Impact(BaseModel):
    target_entity: str = Field(description="The entity affected (e.g., 'Oil Prices', 'Airline Stocks')")
    sentiment: Literal["positive", "negative"] = Field(description="The sentiment of the impact")
    explanation: str = Field(description="Brief explanation of the causal link")

class ImpactList(BaseModel):
    impacts: List[Impact]

class CausalDiscoveryEngine:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="deepseek-chat",
            temperature=0.1,
            openai_api_base="https://api.deepseek.com",
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        self.system_prompt = """You are a Senior Macro Analyst with decades of experience in financial markets and economic theory. 
        Your goal is to identify causal relationships between economic events and financial entities (Assets, Industries, Economic Indicators).
        
        When analyzing an event, identify the most significant direct impacts.
        Focus on logical, first-order and second-order consequences.
        Classify the sentiment of the impact as 'positive' (bullish/beneficial) or 'negative' (bearish/detrimental).
        """

        self.parser = JsonOutputParser(pydantic_object=ImpactList)

    def _get_impacts(self, event_description: str, count: int = 3) -> List[Impact]:
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "Analyze the event: '{event}'. Identify exactly {count} direct impacts. \n{format_instructions}")
        ])

        chain = prompt | self.llm | self.parser

        try:
            result = chain.invoke({
                "event": event_description, 
                "count": count,
                "format_instructions": self.parser.get_format_instructions()
            })
            return [Impact(**i) for i in result['impacts']]
        except Exception as e:
            print(f"Error fetching impacts for '{event_description}': {e}")
            return []

    def _generate_narrative(self, event_text: str, graph: nx.DiGraph) -> str:
        graph_data = self._graph_to_json(graph)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "Based on the following causal graph for the event '{event}', write a single cohesive paragraph (approx. 100 words) summarizing the potential chain reaction. Focus on the most critical risks and opportunities. Use a professional financial tone.\n\nGraph Data: {graph_data}")
        ])

        chain = prompt | self.llm

        try:
            response = chain.invoke({
                "event": event_text,
                "graph_data": json.dumps(graph_data)
            })
            return response.content
        except Exception as e:
            print(f"Error generating narrative: {e}")
            return "Analysis complete. Unable to generate narrative summary."

    def analyze_event(self, event_text: str):
        graph = nx.DiGraph()
        root_id = event_text
        graph.add_node(root_id, label=event_text, type="Event", layer=0)

        direct_impacts = self._get_impacts(event_text, count=3)
        
        for impact in direct_impacts:
            node_id = impact.target_entity
            if not graph.has_node(node_id):
                graph.add_node(node_id, label=node_id, type="Entity", layer=1)
            graph.add_edge(root_id, node_id, sentiment=impact.sentiment, explanation=impact.explanation)

            downstream_event = f"Change in {impact.target_entity} due to {event_text}"
            downstream_impacts = self._get_impacts(downstream_event, count=2)

            for sub_impact in downstream_impacts:
                sub_node_id = sub_impact.target_entity
                if not graph.has_node(sub_node_id):
                    graph.add_node(sub_node_id, label=sub_node_id, type="Entity", layer=2)
                graph.add_edge(node_id, sub_node_id, sentiment=sub_impact.sentiment, explanation=sub_impact.explanation)

        narrative = self._generate_narrative(event_text, graph)
        result = self._graph_to_json(graph)
        result['narrative'] = narrative
        return result

    def _graph_to_json(self, graph: nx.DiGraph):
        nodes = []
        for n, attrs in graph.nodes(data=True):
            nodes.append({
                "id": n,
                "label": attrs.get("label", n),
                "type": attrs.get("type", "Entity"),
                "layer": attrs.get("layer", 0)
            })
        
        edges = []
        for u, v, attrs in graph.edges(data=True):
            edges.append({
                "source": u,
                "target": v,
                "sentiment": attrs.get("sentiment", "neutral"),
                "explanation": attrs.get("explanation", "")
            })
            
        return {"nodes": nodes, "edges": edges}