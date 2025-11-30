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

class ValidationResult(BaseModel):
    valid: bool = Field(description="Whether the causal link is logical and probable")
    reasoning: str = Field(description="Explanation for the validation decision")

class CausalDiscoveryEngine:
    def __init__(self):
        # Agent A: The Macro Detective (Creative Generator)
        self.detective = ChatOpenAI(
            model="deepseek-chat",
            temperature=0.7,  # Higher temperature for creativity
            openai_api_base="https://api.deepseek.com",
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Agent B: The Risk Officer (Critical Reviewer)
        self.reviewer = ChatOpenAI(
            model="deepseek-chat",
            temperature=0.1,  # Lower temperature for consistency
            openai_api_base="https://api.deepseek.com",
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        self.detective_prompt = """You are a VISIONARY MACRO STRATEGIST with a talent for spotting non-obvious connections.
        Your role is to generate creative, second-order causal impacts that others might miss.
        Think beyond the obvious - consider:
        - Cross-market spillovers
        - Behavioral finance effects
        - Political economy dynamics
        - Supply chain ripple effects
        
        Be bold but grounded in economic theory."""
        
        self.reviewer_prompt = """You are a CONSERVATIVE RISK OFFICER with decades of experience.
        Your role is to critically evaluate causal links for logical consistency and probability.
        
        Reject impacts that are:
        - Too speculative or far-fetched
        - Based on weak causal mechanisms
        - Contradicting established economic principles
        
        Only approve impacts with clear, defensible causal chains."""
        
        self.impact_parser = JsonOutputParser(pydantic_object=ImpactList)
        self.validation_parser = JsonOutputParser(pydantic_object=ValidationResult)

    def _get_impacts(self, event_description: str, count: int = 3) -> List[Impact]:
        """Multi-Agent workflow: Detective proposes, Reviewer validates"""
        
        # Step 1: Detective generates 5 candidate impacts
        print(f"\n🕵️ Detective analyzing: {event_description[:50]}...")
        
        detective_prompt = ChatPromptTemplate.from_messages([
            ("system", self.detective_prompt),
            ("user", "Analyze the event: '{event}'. Generate exactly 5 potential causal impacts (including non-obvious ones). \n{format_instructions}")
        ])
        
        detective_chain = detective_prompt | self.detective | self.impact_parser
        
        try:
            candidates = detective_chain.invoke({
                "event": event_description,
                "format_instructions": self.impact_parser.get_format_instructions()
            })
            candidate_impacts = [Impact(**i) for i in candidates['impacts']]
            print(f"   Generated {len(candidate_impacts)} candidates")
        except Exception as e:
            print(f"   ❌ Detective error: {e}")
            return []
        
        # Step 2: Reviewer validates each candidate
        validated_impacts = []
        
        for idx, impact in enumerate(candidate_impacts, 1):
            print(f"\n⚖️  Reviewer evaluating #{idx}: {impact.target_entity}")
            
            reviewer_prompt = ChatPromptTemplate.from_messages([
                ("system", self.reviewer_prompt),
                ("user", """Evaluate this causal link:
                
Event: {event}
Proposed Impact: {target} ({sentiment})
Explanation: {explanation}

Is this causal link logical and probable? Return your validation decision.
{format_instructions}""")
            ])
            
            reviewer_chain = reviewer_prompt | self.reviewer | self.validation_parser
            
            try:
                validation = reviewer_chain.invoke({
                    "event": event_description,
                    "target": impact.target_entity,
                    "sentiment": impact.sentiment,
                    "explanation": impact.explanation,
                    "format_instructions": self.validation_parser.get_format_instructions()
                })
                
                result = ValidationResult(**validation)
                
                if result.valid:
                    print(f"   ✅ APPROVED: {result.reasoning[:80]}...")
                    validated_impacts.append(impact)
                else:
                    print(f"   ❌ REJECTED: {result.reasoning[:80]}...")
                
                # Stop once we have enough validated impacts
                if len(validated_impacts) >= count:
                    break
                    
            except Exception as e:
                print(f"   ⚠️  Validation error: {e}")
                continue
        
        print(f"\n✨ Final result: {len(validated_impacts)}/{len(candidate_impacts)} impacts approved\n")
        return validated_impacts[:count]

    def _generate_narrative(self, event_text: str, graph: nx.DiGraph) -> str:
        graph_data = self._graph_to_json(graph)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.detective_prompt),  # Use detective for creative narrative
            ("user", "Based on the following causal graph for the event '{event}', write a single cohesive paragraph (approx. 100 words) summarizing the potential chain reaction. Focus on the most critical risks and opportunities. Use a professional financial tone.\n\nGraph Data: {graph_data}")
        ])

        chain = prompt | self.detective

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
        print(f"\n{'='*60}")
        print(f"🎯 MULTI-AGENT ANALYSIS: {event_text}")
        print(f"{'='*60}")
        
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
        
        print(f"\n{'='*60}")
        print(f"✅ ANALYSIS COMPLETE")
        print(f"{'='*60}\n")
        
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