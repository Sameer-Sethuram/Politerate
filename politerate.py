"""
politerate.py

Highlights political terms in summary text with tooltip definitions.
Provides an interactive learning experience for users unfamiliar with political jargon.
"""

import re
import json
from pathlib import Path
from typing import Optional

DEFAULT_GLOSSARY_PATH = "glossary.json"


DEFAULT_GLOSSARY = {
    "filibuster": {
        "definition": "A parliamentary tactic where a senator speaks for an extended time to delay or prevent a vote on a bill.",
        "category": "legislative process"
    },
    "cloture": {
        "definition": "A procedure to end a filibuster in the U.S. Senate, requiring 60 votes to limit debate.",
        "category": "legislative process"
    },
    "reconciliation": {
        "definition": "A budget process that allows certain legislation to pass the Senate with a simple majority (51 votes) rather than 60.",
        "category": "legislative process"
    },
    "impeachment": {
        "definition": "The process by which Congress can remove a federal official from office for 'high crimes and misdemeanors.'",
        "category": "constitutional powers"
    },
    "quorum": {
        "definition": "The minimum number of members required to be present for a legislative body to conduct business.",
        "category": "legislative process"
    },
    "caucus": {
        "definition": "A meeting of members of a political party to decide on policies, candidate selections, or legislative strategy.",
        "category": "political organization"
    },
    "amendment": {
        "definition": "A formal addition or change to a legislative bill or constitution.",
        "category": "legislative process"
    },
    "pork barrel": {
        "definition": "Legislation that allocates government spending for local projects primarily to benefit a specific congressperson's district.",
        "category": "spending"
    },
    "earmark": {
        "definition": "A provision in legislation that directs funds to a specific project or entity.",
        "category": "spending"
    },
    "gerrymandering": {
        "definition": "The manipulation of electoral district boundaries to favor one party over another.",
        "category": "electoral systems"
    },
    "swing state": {
        "definition": "A state where no single party has dominant support; often decides national elections.",
        "category": "electoral systems"
    },
    "electoral college": {
        "definition": "The body of electors that formally elects the U.S. President; each state has votes equal to its Congress members.",
        "category": "electoral systems"
    },
    "poll tax": {
        "definition": "A tax required to vote, historically used to disenfranchise Black voters. Now prohibited by the 24th Amendment.",
        "category": "voting rights"
    },
    "voter suppression": {
        "definition": "Policies or practices that prevent or discourage people from exercising their right to vote.",
        "category": "voting rights"
    },
    "dark money": {
        "definition": "Political spending where the source of funds is not disclosed, making it difficult to trace campaign contributions.",
        "category": "campaign finance"
    },
    "super PAC": {
        "definition": "Political action committees that can raise unlimited funds but cannot contribute directly to candidates.",
        "category": "campaign finance"
    },
    "lobbying": {
        "definition": "Attempting to influence legislators' decisions on laws and regulations, often on behalf of interest groups.",
        "category": "political influence"
    },
    "veto": {
        "definition": "The President's power to reject legislation passed by Congress; can be overridden by 2/3 vote in both chambers.",
        "category": "executive powers"
    },
    "executive order": {
        "definition": "A directive issued by the President that manages government operations without Congressional approval.",
        "category": "executive powers"
    },
    "regulatory capture": {
        "definition": "When regulatory agencies act in favor of the industry they regulate rather than the public interest.",
        "category": "governance"
    },
    "bipartisan": {
        "definition": "Supported or created by two political parties that usually oppose each other's policies, typically Democrats and Republicans.",
        "category": "political organization"
    },
    "partisan": {
        "definition": "Strongly supporting or biased toward a particular political party rather than approaching an issue neutrally.",
        "category": "political organization"
    },
    "incumbent": {
        "definition": "A person currently holding a political office, especially one running for reelection.",
        "category": "electoral systems"
    },
    "primary election": {
        "definition": "An election in which party members select the candidate who will represent the party in the general election.",
        "category": "electoral systems"
    },
    "general election": {
        "definition": "The final election where voters choose among the candidates nominated by each party for a given office.",
        "category": "electoral systems"
    },
    "redistricting": {
        "definition": "The process of redrawing legislative district boundaries, typically after a census, to reflect population changes.",
        "category": "electoral systems"
    },
    "census": {
        "definition": "The official count of the U.S. population every ten years, used to allocate congressional seats and federal funding.",
        "category": "governance"
    },
    "checks and balances": {
        "definition": "The constitutional principle that each branch of government (legislative, executive, judicial) has powers that limit the others.",
        "category": "constitutional powers"
    },
    "separation of powers": {
        "definition": "The division of government responsibilities into three branches so no single branch holds all authority.",
        "category": "constitutional powers"
    },
    "judicial review": {
        "definition": "The power of courts to determine whether acts of Congress, the executive, or states violate the Constitution.",
        "category": "constitutional powers"
    },
    "supermajority": {
        "definition": "A number of votes much larger than a simple majority, typically two-thirds, required for actions like overriding a veto or amending the Constitution.",
        "category": "legislative process"
    },
    "majority leader": {
        "definition": "The leader of the majority party in a legislative chamber, responsible for setting the legislative agenda.",
        "category": "political organization"
    },
    "minority leader": {
        "definition": "The leader of the minority party in a legislative chamber, responsible for coordinating opposition strategy.",
        "category": "political organization"
    },
    "whip": {
        "definition": "A party official in a legislature who ensures members vote along party lines and tracks vote counts.",
        "category": "political organization"
    },
    "appropriation": {
        "definition": "A legislative act that authorizes the government to spend money from the Treasury for specific purposes.",
        "category": "spending"
    },
    "continuing resolution": {
        "definition": "A temporary funding measure that keeps the federal government operating at current levels when regular appropriations haven't passed.",
        "category": "spending"
    },
    "government shutdown": {
        "definition": "A period when non-essential federal agencies stop operating because Congress has not passed funding legislation.",
        "category": "spending"
    },
    "PAC": {
        "definition": "A Political Action Committee that pools contributions from members to donate to candidates for or against specific legislation.",
        "category": "campaign finance"
    },
    "Citizens United": {
        "definition": "A 2010 Supreme Court case that allowed unlimited independent political spending by corporations and unions, leading to the rise of super PACs.",
        "category": "campaign finance"
    },
    "gag order": {
        "definition": "A court-issued ruling that restricts parties in a legal case from speaking publicly about it.",
        "category": "governance"
    },
    "subpoena": {
        "definition": "A legal document ordering someone to testify or produce evidence in a court or legislative hearing.",
        "category": "governance"
    },
    "bill": {
        "definition": "A proposed law under consideration by a legislature; becomes law after passing both chambers and being signed by the executive.",
        "category": "legislative process"
    },
    "rider": {
        "definition": "An additional provision attached to a bill, often unrelated to the main subject, used to pass measures that might not succeed on their own.",
        "category": "legislative process"
    },
    "omnibus bill": {
        "definition": "A single document that packages many separate bills together, often covering diverse or unrelated topics.",
        "category": "legislative process"
    },
    "town hall": {
        "definition": "A public meeting where elected officials hear questions and concerns directly from constituents.",
        "category": "political organization"
    },
    "constituent": {
        "definition": "A member of the community represented by an elected official.",
        "category": "political organization"
    },
    "ratification": {
        "definition": "The formal approval of a treaty, constitutional amendment, or agreement by a legislative body.",
        "category": "constitutional powers"
    },
    "executive privilege": {
        "definition": "The power of the President to withhold information from other branches of government, especially regarding confidential communications.",
        "category": "executive powers"
    },
    "pocket veto": {
        "definition": "An indirect veto that occurs when the President takes no action on a bill within 10 days and Congress has adjourned, preventing it from becoming law.",
        "category": "executive powers"
    }
}


class TermHighlighter:
    def __init__(self, glossary_path: Optional[str] = None):
        if glossary_path and Path(glossary_path).exists():
            with open(glossary_path, "r") as f:
                self.glossary = json.load(f)
        else:
            self.glossary = DEFAULT_GLOSSARY

        self.term_pattern = self._build_pattern()

    def _build_pattern(self) -> re.Pattern:
        terms = sorted(self.glossary.keys(), key=len, reverse=True)
        pattern = r"\b(" + "|".join(re.escape(t) for t in terms) + r")\b"
        return re.compile(pattern, re.IGNORECASE)

    def highlight(self, text: str, css_class: str = "politerate-term") -> str:
        def replace_term(match):
            term = match.group(0).lower()
            term_info = self.glossary.get(term, self.glossary.get(next((k for k in self.glossary if k.lower() == term), None)))

            if term_info:
                definition = term_info.get("definition", "").replace('"', "&quot;")
                category = term_info.get("category", "")
                tooltip = f"{category}: {definition}" if category else definition
                return f'<span class="{css_class}" title="{tooltip}" data-term="{term}">{match.group(0)}</span>'
            return match.group(0)

        return self.term_pattern.sub(replace_term, text)

    def get_term_definitions(self, text: str) -> list[dict]:
        found_terms = set(self.term_pattern.findall(text.lower()))
        definitions = []

        for term in found_terms:
            term_info = self.glossary.get(term)
            if term_info:
                definitions.append({
                    "term": term,
                    "definition": term_info.get("definition", ""),
                    "category": term_info.get("category", "")
                })

        return definitions

    def find_terms_with_sources(self, articles: list[dict]) -> dict:
        """Returns dict mapping term -> list of {source, url} for each article containing the term."""
        term_article_map = {}

        for article in articles:
            text = article.get("text", "")
            found = set(self.term_pattern.findall(text.lower()))

            for term in found:
                if term not in term_article_map:
                    term_article_map[term] = []

                term_article_map[term].append({
                    "source": article.get("source", "Unknown Source"),
                    "url": article.get("url", "#"),
                    "title": article.get("title", "Untitled Article")
                })

        return term_article_map

    def add_term(self, term: str, definition: str, category: str = "general") -> None:
        self.glossary[term.lower()] = {
            "definition": definition,
            "category": category
        }
        self.term_pattern = self._build_pattern()

    def save_glossary(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.glossary, f, indent=2)


def highlight_text(text: str, glossary_path: Optional[str] = None) -> str:
    highlighter = TermHighlighter(glossary_path)
    return highlighter.highlight(text)


def get_definitions(text: str, glossary_path: Optional[str] = None) -> list[dict]:
    highlighter = TermHighlighter(glossary_path)
    return highlighter.get_term_definitions(text)


if __name__ == "__main__":
    test_text = """
    The Senate voted on the filibuster reform bill today, with reconciliation
    being discussed as an alternative approach. The reconciliation process could
    bypass the 60-vote threshold needed to end a filibuster.
    """

    print("\n=== Politerate Term Highlighter Test ===\n")
    print("Original text:")
    print(test_text)

    print("\nHighlighted HTML:")
    highlighter = TermHighlighter()
    highlighted = highlighter.highlight(test_text)
    print(highlighted)

    print("\nDetected terms:")
    definitions = highlighter.get_term_definitions(test_text)
    for d in definitions:
        print(f"  - {d['term']} ({d['category']}): {d['definition']}")
