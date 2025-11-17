"""
Test cases for agent evaluation
Defines various test scenarios to evaluate agent performance
"""
from app.core.evaluation import TestCase


# Calendar-related test cases
CALENDAR_TEST_CASES = [
    TestCase(
        id="calendar_001",
        name="Query eventi oggi",
        description="Agent should retrieve today's calendar events",
        input_message="Quali eventi ho oggi?",
        expected_tools=["get_calendar_events"],
        expected_keywords=["evento", "oggi", "calendario"],
        expected_response_type="calendar_query",
        category="calendar",
        min_response_length=20,
    ),
    TestCase(
        id="calendar_002",
        name="Query eventi domani",
        description="Agent should retrieve tomorrow's calendar events",
        input_message="Cosa ho in programma domani?",
        expected_tools=["get_calendar_events"],
        expected_keywords=["domani", "programma"],
        expected_response_type="calendar_query",
        category="calendar",
        min_response_length=20,
    ),
    TestCase(
        id="calendar_003",
        name="Query eventi questa settimana",
        description="Agent should retrieve this week's calendar events",
        input_message="Mostrami gli eventi di questa settimana",
        expected_tools=["get_calendar_events"],
        expected_keywords=["settimana", "evento"],
        expected_response_type="calendar_query",
        category="calendar",
        min_response_length=20,
    ),
]

# Email-related test cases
EMAIL_TEST_CASES = [
    TestCase(
        id="email_001",
        name="Query email non lette",
        description="Agent should retrieve unread emails",
        input_message="Hai email non lette?",
        expected_tools=["get_emails"],
        expected_keywords=["email", "non lette"],
        expected_response_type="email_query",
        category="email",
        min_response_length=20,
    ),
    TestCase(
        id="email_002",
        name="Query email di oggi",
        description="Agent should retrieve today's emails",
        input_message="Mostrami le email ricevute oggi",
        expected_tools=["get_emails"],
        expected_keywords=["email", "oggi"],
        expected_response_type="email_query",
        category="email",
        min_response_length=20,
    ),
    TestCase(
        id="email_003",
        name="Riassunto email",
        description="Agent should summarize emails",
        input_message="Fammi un riassunto delle ultime email",
        expected_tools=["summarize_emails"],
        expected_keywords=["riassunto", "email"],
        expected_response_type="email_query",
        category="email",
        min_response_length=30,
    ),
]

# Web search test cases
WEB_SEARCH_TEST_CASES = [
    TestCase(
        id="web_001",
        name="Ricerca web semplice",
        description="Agent should perform web search",
        input_message="Cerca informazioni su Python 3.13",
        expected_tools=["web_search"],
        expected_keywords=["Python", "3.13"],
        expected_response_type="web_search",
        category="web_search",
        min_response_length=50,
    ),
    TestCase(
        id="web_002",
        name="Ricerca notizie",
        description="Agent should search for recent news",
        input_message="Cerca le ultime notizie su AI",
        expected_tools=["web_search"],
        expected_keywords=["notizie", "AI"],
        expected_response_type="web_search",
        category="web_search",
        min_response_length=50,
    ),
]

# Google Maps test cases
MAPS_TEST_CASES = [
    TestCase(
        id="maps_001",
        name="Ricerca luoghi",
        description="Agent should search for places using Google Maps",
        input_message="Cerca ristoranti italiani a Ginevra",
        expected_tools=["mcp_maps_search_places"],
        expected_keywords=["ristorante", "italiano", "Ginevra"],
        expected_response_type="maps_query",
        category="maps",
        min_response_length=30,
    ),
    TestCase(
        id="maps_002",
        name="Calcolo direzioni",
        description="Agent should calculate directions using Google Maps",
        input_message="Come arrivo da Ginevra a Losanna?",
        expected_tools=["mcp_maps_directions"],
        expected_keywords=["direzione", "Ginevra", "Losanna"],
        expected_response_type="maps_query",
        category="maps",
        min_response_length=30,
    ),
]

# Memory test cases
MEMORY_TEST_CASES = [
    TestCase(
        id="memory_001",
        name="Query memoria",
        description="Agent should retrieve information from memory",
        input_message="Cosa ricordi di me?",
        expected_tools=None,  # Memory retrieval is internal
        expected_keywords=["ricordo", "memoria"],
        expected_response_type="memory_query",
        category="memory",
        min_response_length=20,
    ),
    TestCase(
        id="memory_002",
        name="Query contesto sessione",
        description="Agent should use session context",
        input_message="Di cosa stavamo parlando?",
        expected_tools=None,
        expected_keywords=["parlavamo", "sessione"],
        expected_response_type="memory_query",
        category="memory",
        min_response_length=20,
    ),
]

# General conversation test cases
GENERAL_TEST_CASES = [
    TestCase(
        id="general_001",
        name="Saluto semplice",
        description="Agent should respond to simple greeting",
        input_message="Ciao, come stai?",
        expected_tools=None,
        expected_keywords=["ciao", "stai"],
        expected_response_type="conversation",
        category="general",
        min_response_length=10,
    ),
    TestCase(
        id="general_002",
        name="Domanda informativa",
        description="Agent should answer informational questions",
        input_message="Cos'è Python?",
        expected_tools=None,
        expected_keywords=["Python"],
        expected_response_type="conversation",
        category="general",
        min_response_length=30,
    ),
]

# All test cases
ALL_TEST_CASES = (
    CALENDAR_TEST_CASES +
    EMAIL_TEST_CASES +
    WEB_SEARCH_TEST_CASES +
    MAPS_TEST_CASES +
    MEMORY_TEST_CASES +
    GENERAL_TEST_CASES
)


def get_test_cases_by_category(category: str) -> list[TestCase]:
    """Get test cases filtered by category"""
    return [tc for tc in ALL_TEST_CASES if tc.category == category]


def get_test_cases_by_id(test_ids: list[str]) -> list[TestCase]:
    """Get test cases by their IDs"""
    return [tc for tc in ALL_TEST_CASES if tc.id in test_ids]

